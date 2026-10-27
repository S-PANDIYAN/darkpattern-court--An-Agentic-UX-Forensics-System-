/**
 * DarkShield — Background Service Worker
 * Handles message passing, side panel opening, and ML inference.
 */

import { pipeline, env } from './lib/transformers.min.js';

// Configure Transformers.js for Chrome Extension
env.allowLocalModels = true;
env.allowRemoteModels = false;
env.useBrowserCache = false;
env.localModelPath = chrome.runtime.getURL('/');
env.backends.onnx.wasm.wasmPaths = chrome.runtime.getURL('lib/wasm/');
env.backends.onnx.wasm.numThreads = 1; // Required for Manifest V3 Service Workers

class PipelineSingleton {
    static instance = null;

    static async getInstance(progress_callback = null) {
        if (this.instance === null) {
            // We use the same name as the folder where our model is stored.
            // But actually Transformers.js expects the model parameter to be the path.
            // If localModelPath is set, we can just use the folder name or '.' if we pass the full URL.
            // It will load chrome-extension://<id>/model/config.json etc.
            this.instance = pipeline('text-classification', 'model', {
                quantized: true
            });
        }
        return this.instance;
    }
}

// Pre-load the model when the background script starts
PipelineSingleton.getInstance().catch(err => console.error("Failed to load model:", err));

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'OPEN_SIDE_PANEL') {
        (async () => {
            try {
                const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                if (tab) {
                    await chrome.sidePanel.open({ windowId: tab.windowId });
                    sendResponse({ success: true });
                }
            } catch (err) {
                console.error('Failed to open side panel:', err);
                sendResponse({ success: false, error: err.message });
            }
        })();
        return true;
    }

    if (message.type === 'GET_RESULTS') {
        chrome.storage.local.get('scanResults').then(data => {
            sendResponse({ results: data.scanResults || null });
        }).catch(() => sendResponse({ results: null }));
        return true;
    }

    if (message.type === 'RUN_INFERENCE') {
        (async () => {
            try {
                const classifier = await PipelineSingleton.getInstance();
                const texts = message.texts; // Array of strings
                
                // Run inference with top_k to get ALL class probabilities.
                // This lets the content script do margin-based filtering
                // using the model's own uncertainty (not external rules).
                const output = await classifier(texts, { top_k: 8 });
                
                // output is now an array of arrays:
                // [[{label, score}, {label, score}, ...], ...]
                // Each inner array has all 8 classes sorted by score.
                
                // Normalize: transform each prediction into a single object with
                // the top non-Benign label, its score, and the Benign score.
                const predictions = [];
                for (let i = 0; i < texts.length; i++) {
                    const allClasses = Array.isArray(output[i]) ? output[i] : [output[i]];
                    
                    // Find the Benign class score
                    const benignEntry = allClasses.find(c => c.label === 'Benign');
                    const benignScore = benignEntry ? benignEntry.score : 0;
                    
                    // Find the top non-Benign class
                    const topDarkPattern = allClasses.find(c => c.label !== 'Benign');
                    
                    if (topDarkPattern && topDarkPattern.score > benignScore) {
                        predictions.push({
                            label: topDarkPattern.label,
                            score: topDarkPattern.score,
                            benignScore: benignScore
                        });
                    } else {
                        predictions.push({
                            label: 'Benign',
                            score: benignScore,
                            benignScore: benignScore
                        });
                    }
                }

                
                // Add LIME explanations for positive detections
                for (let i = 0; i < predictions.length; i++) {
                    const pred = predictions[i];
                    if (pred.label !== 'Benign' && pred.score > 0.90) {
                        const text = texts[i];
                        const words = text.split(/\s+/).filter(w => w.length > 0);
                        
                        // Limit LIME to reasonably sized sentences to avoid freezing the browser
                        if (words.length <= 40) {
                            const perturbedTexts = [];
                            for (let j = 0; j < words.length; j++) {
                                const newWords = [...words];
                                newWords.splice(j, 1);
                                perturbedTexts.push(newWords.join(' '));
                            }
                            
                            // Run inference on all perturbed texts
                            if (perturbedTexts.length > 0) {
                                const perturbedOutputs = await classifier(perturbedTexts);
                                
                                const wordImportance = [];
                                for (let j = 0; j < words.length; j++) {
                                    // Find probability of the original label in the perturbed output
                                    // Note: depending on the pipeline, it might just return the top class
                                    // If top class changed, the score drop is significant.
                                    let newScore = 0;
                                    // In transformers.js text-classification, if it returns single top class:
                                    if (Array.isArray(perturbedOutputs[j])) {
                                        const match = perturbedOutputs[j].find(o => o.label === pred.label);
                                        newScore = match ? match.score : 0;
                                    } else {
                                        newScore = perturbedOutputs[j].label === pred.label ? perturbedOutputs[j].score : 0;
                                    }
                                    
                                    const drop = pred.score - newScore;
                                    wordImportance.push({ word: words[j], drop });
                                }
                                
                                // Sort by drop in probability (highest drop = most important)
                                wordImportance.sort((a, b) => b.drop - a.drop);
                                
                                // Get top 3 words (excluding stop words optionally, but simple top 3 is fine)
                                pred.limeWords = wordImportance.slice(0, 3).filter(w => w.drop > 0.05).map(w => w.word);
                            }
                        }
                    }
                }

                sendResponse({ success: true, predictions });
            } catch (err) {
                console.error("Inference error:", err);
                sendResponse({ success: false, error: err.message });
            }
        })();
        return true; // Keep channel open
    }

    if (message.type === 'SCAN_COMPLETE') {
        (async () => {
            await chrome.storage.local.set({ scanResults: message.data });
            const count = message.data.detections.length;
            await chrome.action.setBadgeText({ text: count > 0 ? String(count) : '' });
            await chrome.action.setBadgeBackgroundColor({ color: count > 0 ? '#ef4444' : '#22c55e' });
            sendResponse({ success: true });
        })();
        return true;
    }
});
