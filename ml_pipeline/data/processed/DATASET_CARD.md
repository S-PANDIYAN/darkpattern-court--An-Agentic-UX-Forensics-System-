# Dataset Card: Lumichats Dark Pattern Detection Dataset

## Dataset Summary

A multi-class text classification dataset for detecting dark patterns on Indian websites. Contains **2,787 labeled text segments** across 8 categories (7 dark pattern types + 1 benign/None class), sourced from 150+ Indian web platforms and supplemented with a Kaggle dark patterns corpus.

## Dataset Sources

| Source | Rows | Description |
|--------|------|-------------|
| Custom web scraping (150 Indian websites) | 42 | Selenium-based scraping of e-commerce, travel, food delivery, job portals, financial services |
| Kaggle Dark Patterns Dataset | 2,645 | Pre-labeled dataset with categories harmonized to our schema |
| Handcrafted augmentation | 100 | Expert-written examples for rare classes (Trick Questions, Hidden Costs, Roach Motel) |

## Annotation Process

1. **Web Scraping**: [scraper.py](scraper.py) used Selenium + BeautifulSoup to extract visible text chunks (10-400 chars) from 150 Indian websites across 6 sectors.
2. **Label Studio Annotation**: 42 text chunks were manually annotated using Label Studio with the 7-category schema defined by the CCPA 2023 dark pattern guidelines.
3. **Kaggle Harmonization**: The Kaggle dataset's native labels (Scarcity, Urgency, Sneaking, Obstruction, etc.) were mapped to our 7-category schema via [phase1_harmonize.py](phase1_harmonize.py).
4. **Augmentation**: Handcrafted examples added for Trick Questions (30), Hidden Costs (40), and Roach Motel (30) to ensure minimum representation.

## Label Schema

| Category | Description | Count |
|----------|-------------|-------|
| None | Benign/normal text, not a dark pattern | 1,362 |
| Urgency or Scarcity | Creates false sense of limited time/stock | 560 |
| Disguised Ads | Ads camouflaged as content or social proof | 334 |
| Misdirection | Directs attention away from unfavorable options | 226 |
| Confirmshaming | Shames users into accepting via guilt-laden language | 156 |
| Roach Motel | Easy to sign up, extremely hard to cancel | 62 |
| Hidden Costs | Undisclosed fees revealed late in the flow | 57 |
| Trick Questions | Confusing double negatives or ambiguous opt-in/out phrasing | 30 |

## Data Splits

| Split | Rows | Percentage |
|-------|------|------------|
| Train | 1,950 | 70% |
| Validation | 418 | 15% |
| Test | 419 | 15% |

Splits are stratified by label to maintain proportional class representation.

## Limitations

- **Class imbalance**: Trick Questions (30 examples) and Hidden Costs (57 examples) are severely underrepresented relative to None (1,362).
- **Augmentation bias**: ~100 examples are handcrafted rather than scraped from live websites, which may not capture the full diversity of real-world phrasing.
- **Single annotator**: The custom 42-row dataset was labeled by a single annotator without inter-annotator agreement metrics.
- **Temporal snapshot**: Websites change frequently; the scraped data represents a point-in-time snapshot (June 2026).
- **Geographic scope**: Focused on Indian platforms; patterns from other regions may differ.

## Usage

```python
import pandas as pd
train_df = pd.read_csv("train.csv")
val_df = pd.read_csv("val.csv")
test_df = pd.read_csv("test.csv")
```

## Citation

This dataset was created as part of the Lumichats Social Initiative internship program for Dark Pattern Detection in India.
