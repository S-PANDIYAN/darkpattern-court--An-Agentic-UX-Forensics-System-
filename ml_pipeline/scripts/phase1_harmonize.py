import pandas as pd
import os

# ==========================================
# 1. DEFINE FILE PATHS & TARGET CATEGORIES
# ==========================================
KAGGLE_FILE = "kaggle_dataset.csv"  
MY_DATA_FILE = "dataset.csv"     
OUTPUT_FILE = "lumichats_master_dataset.csv"

# The strict 7 categories required for Lumichats
LUMICHATS_CATEGORIES = [
    "Urgency or Scarcity", 
    "Confirmshaming", 
    "Hidden Costs", 
    "Trick Questions", 
    "Roach Motel", 
    "Disguised Ads", 
    "Misdirection",
    "None" # Baseline class for normal/benign text
]

# ==========================================
# 2. THE HARMONIZATION MAP
# ==========================================
LABEL_MAP = {
    "Scarcity": "Urgency or Scarcity",
    "Urgency": "Urgency or Scarcity",
    "Sneaking": "Hidden Costs",
    "Hidden Subscription": "Hidden Costs",
    "Misdirection": "Misdirection",
    "Trick Questions": "Trick Questions",
    "Obstruction": "Roach Motel",
    "Hard to Cancel": "Roach Motel",
    "Confirmshaming": "Confirmshaming",
    "Forced Action": "Confirmshaming",
    "Disguised Ads": "Disguised Ads",
    "Social Proof": "Disguised Ads",
    "Not Dark Pattern": "None",
    "Benign": "None",
    "0": "None"
}

def harmonize_data():
    print("🚀 Starting Data Harmonization Pipeline...")
    dataframes_to_merge = []

    # ==========================================
    # 3. PROCESS YOUR LABEL STUDIO DATA
    # ==========================================
    if os.path.exists(MY_DATA_FILE):
        print(f"Loading Label Studio export: {MY_DATA_FILE}")
        my_df = pd.read_csv(MY_DATA_FILE)
        
        # Isolate exactly the columns from your screenshot
        if 'text' in my_df.columns and 'dark_pattern' in my_df.columns:
            my_df = my_df[['text', 'dark_pattern']].copy()
            my_df = my_df.rename(columns={'dark_pattern': 'label'})
            
            # Fill all blank cells with our baseline category
            my_df['label'] = my_df['label'].fillna('None')
            dataframes_to_merge.append(my_df)
            print(f"✅ Added {len(my_df)} custom Label Studio rows.")
        else:
            print("⚠️ Warning: Could not find 'text' and 'dark_pattern' columns in your custom CSV.")
    else:
        print(f"⚠️ Warning: Custom data {MY_DATA_FILE} not found. Skipping.")

    # ==========================================
    # 4. PROCESS KAGGLE DATASET
    # ==========================================
    if os.path.exists(KAGGLE_FILE):
        print(f"Loading Kaggle data: {KAGGLE_FILE}")
        kaggle_df = pd.read_csv(KAGGLE_FILE)
        
        # Parse exact Kaggle columns from your screenshot
        if 'Title' in kaggle_df.columns and 'Category' in kaggle_df.columns:
            kaggle_df = kaggle_df[['Title', 'Category']].copy()
            kaggle_df = kaggle_df.rename(columns={'Title': 'text', 'Category': 'label'})
            
            # Map Kaggle labels to Lumichats categories
            kaggle_df['label'] = kaggle_df['label'].map(LABEL_MAP).fillna('None')
            
            dataframes_to_merge.append(kaggle_df)
            print(f"✅ Added {len(kaggle_df)} Kaggle rows.")
        else:
            print("❌ Error: Kaggle columns 'Title' and 'Category' not found. Check your CSV.")
    else:
        print(f"❌ Error: Kaggle dataset {KAGGLE_FILE} not found. Please download it.")
        return

    # ==========================================
    # 5. MERGE, CLEAN, AND SHUFFLE
    # ==========================================
    if not dataframes_to_merge:
        print("❌ Error: No data to merge. Exiting.")
        return

    print("\nMerging datasets...")
    master_df = pd.concat(dataframes_to_merge, ignore_index=True)
    
    # Ensure text is treated as strings
    master_df['text'] = master_df['text'].astype(str)
    
    # Drop exact string duplicates to prevent model memorization
    initial_len = len(master_df)
    master_df = master_df.drop_duplicates(subset=['text'])
    print(f"Removed {initial_len - len(master_df)} duplicate rows.")
    
    # Drop any rows that are completely empty
    master_df = master_df.dropna(subset=['text', 'label'])
    
    # Filter strictly to our 7 categories + None
    master_df = master_df[master_df['label'].isin(LUMICHATS_CATEGORIES)]
    
    # Shuffle the dataset thoroughly (Critical for training)
    master_df = master_df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Save the final Master Dataset
    master_df.to_csv(OUTPUT_FILE, index=False)
    
    print("\n🎉 Harmonization Complete!")
    print(f"Master dataset saved to: {OUTPUT_FILE}")
    print("\n--- Final Category Distribution ---")
    print(master_df['label'].value_counts())

if __name__ == "__main__":
    harmonize_data()
