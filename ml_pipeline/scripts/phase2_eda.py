"""
Phase 2: Dataset Fix, Augmentation, EDA & Stratified Split
============================================================
- Fixes NaN labels → "None"
- Adds handcrafted examples for Trick Questions (0 examples), 
  Hidden Costs (17), and Roach Motel (32)
- Generates class distribution & text length charts
- Performs stratified 70/15/15 train/val/test split
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
import os
import json

# ============================================================
# 1. AUGMENTED EXAMPLES FOR RARE CLASSES
# ============================================================

TRICK_QUESTIONS_EXAMPLES = [
    "Uncheck this box if you prefer not to receive marketing emails",
    "Do you disagree with not receiving our newsletter? Select No to opt out",
    "By proceeding you agree to share your data unless you opt out below",
    "I do not wish to not receive promotional offers",
    "Click here if you don't want us to not share your information with partners",
    "Are you sure you don't want to miss out on exclusive deals?",
    "Deselect to opt out of sharing your browsing history with advertisers",
    "Would you like to not unsubscribe from our mailing list?",
    "Check this box to indicate you do not want to opt out of data collection",
    "Unless you choose otherwise your data will be shared with our partners for better offers",
    "Tick here if you do not wish to not participate in our rewards program",
    "Do you wish to decline opting in to receive personalized recommendations?",
    "I want to miss exclusive member benefits and pay full price",
    "Skip this step only if you do not want personalised ads turned off",
    "By not unchecking this option you agree to third-party cookies",
    "Leave unchecked to not receive important account updates and offers",
    "Select No if you do not disagree with our updated privacy terms",
    "I do not want to save money with automatic renewal",
    "Unsubscribe from essential service notifications? This cannot be undone",
    "Do you not want to keep your account secure with two-factor authentication?",
    "I prefer not to get free shipping on future orders",
    "Choose to decline if you want to continue without price drop alerts",
    "Don't check this unless you want to disable all future discounts on your account",
    "Would you rather not have your payment details remembered for faster checkout?",
    "I understand that by declining I waive any right to cashback rewards",
    "Untick if you wish to forfeit your loyalty points accumulated this year",
    "Are you sure you want to turn off smart savings recommendations?",
    "Skip verification to browse without personalised security protection",
    "By opting out you acknowledge slower delivery times on all future orders",
    "I choose not to protect my purchase with the recommended guarantee",
]

HIDDEN_COSTS_EXAMPLES = [
    "Service fee of Rs 49 will be added at checkout",
    "Platform fee: Rs 5 added to your order total",
    "Convenience charge of Rs 30 applies for online payment",
    "A handling fee of Rs 25 has been included in your total",
    "Additional GST charges applicable. Final price may vary",
    "Packaging charges: Rs 15 per item applies on this order",
    "Delivery charge of Rs 40 will be calculated at checkout",
    "Surge pricing is currently active. Prices are 1.5x the base rate",
    "Insurance fee of Rs 99 has been pre-selected for your protection",
    "Assembly charges of Rs 500 not included in the displayed price",
    "Final price includes a non-refundable booking fee of Rs 199",
    "A restocking fee of 15% applies to all returned electronics",
    "Priority listing fee of Rs 299 has been added to boost your ad",
    "Transaction processing fee of 2.5% applies to international cards",
    "A cancellation charge of Rs 100 will apply if you cancel within 24 hours",
    "Mandatory travel insurance of Rs 249 has been added to your booking",
    "Environmental levy of Rs 10 included in the total amount",
    "Night delivery surcharge of Rs 50 applies between 10 PM and 6 AM",
    "Credit card surcharge of 1.5% applicable on all card payments",
    "Your total includes a tip of Rs 20 which you can modify at checkout",
    "Price shown is exclusive of taxes. Applicable GST will be added at payment",
    "Rental security deposit of Rs 2000 required. Refundable after 30 days",
    "Documentation charges of Rs 500 apply for loan processing",
    "Peak hour charges: an extra Rs 30 applies between 8-10 AM",
    "An auto-applied donation of Rs 10 to our charity partner has been added",
    "Internet handling fee of Rs 29 for online ticket bookings",
    "Fuel surcharge of Rs 75 has been added to your delivery",
    "Premium packaging fee of Rs 99 pre-selected for gift wrapping",
    "A resort fee of Rs 750 per night is not included in the room rate",
    "Your subscription renews at Rs 999/month after the Rs 1 trial ends",
    "Exam registration includes a non-refundable processing fee of Rs 150",
    "Express checkout fee of Rs 19 for instant order confirmation",
    "Amendment charges of Rs 500 per passenger apply for date changes",
    "ATM withdrawal fee of Rs 21 per transaction after 5 free withdrawals",
    "Seat selection charges starting from Rs 200 applicable on this flight",
    "Your final bill may include a service charge of 10% at the restaurant's discretion",
    "A cleaning fee of Rs 1500 will be applied to your vacation rental booking",
    "Late payment penalty of Rs 50 per day applicable after the due date",
    "Installation charges of Rs 399 apply and are collected at delivery",
    "Your cart total does not include the mandatory Rs 49 safety compliance fee",
]

ROACH_MOTEL_EXAMPLES = [
    "To cancel your subscription please call our customer care between 10 AM and 5 PM on weekdays",
    "Account deletion requires submitting a written request via registered post to our headquarters",
    "To unsubscribe please email cancellation@company.com and wait 7-10 business days for processing",
    "You must visit our nearest branch in person with a valid photo ID to close your account",
    "Cancellation is only available by contacting customer support via phone. Chat support cannot process cancellations",
    "To deactivate auto-renewal please navigate to Settings then Account then Subscriptions then Manage then Cancel",
    "Your cancellation request has been received. A retention specialist will call you within 48 hours to confirm",
    "Please complete this 15-step verification process to proceed with your account deletion",
    "Unsubscribing requires you to first download your data, then verify your identity, then wait for approval",
    "Before we cancel, would you like to consider our discounted plan at 50% off? Are you really sure you want to leave?",
    "Free trial activated! Note: cancellation must be done 48 hours before the trial ends or you will be charged",
    "To cancel please provide your original order number, account creation date, and last four digits of your payment card",
    "We're sorry to see you go. Your cancellation will take effect after your current billing cycle ends in 27 days",
    "Account removal requires approval from our team. Typical processing time is 30 to 90 days",
    "You can only cancel during the first 3 days of your billing cycle. Please try again next month",
    "Are you sure? You'll lose all your data, purchase history, and reward points. This action cannot be reversed",
    "To downgrade from Premium you must first cancel your current plan and wait 30 days before re-subscribing",
    "Please note that cancellation will forfeit your locked-in promotional rate permanently",
    "Cancellation requires a minimum notice period of 60 days before your next renewal date",
    "To opt out of our loyalty program please fill out this form and attach a scanned copy of your government ID",
    "Your subscription is part of a bundle. To cancel you must call and cancel each service separately",
    "Unsubscribe process: Step 1 of 6. Why are you leaving? Please select all reasons that apply",
    "You signed a 12-month commitment. Early termination incurs a fee equal to your remaining months",
    "To delete your profile please first remove all saved addresses, payment methods, and linked accounts manually",
    "We need 14 business days to verify your identity before we can process the account closure",
    "Cancellation by phone only. Current hold time: approximately 45 minutes",
    "Your account contains active orders. You must wait until all deliveries are complete before requesting deletion",
    "Sorry, this plan cannot be cancelled online. Please visit our support centre during business hours",
    "To close your account, first transfer your remaining wallet balance, which may take 5-7 business days",
    "Please confirm your cancellation by clicking the link in the email we sent. The link expires in 2 hours",
]

BENIGN_HARD_NEGATIVES = [
    "100+ bought in past month",
    "200+ bought in past month",
    "300+ bought in past month",
    "400+ bought in past month",
    "500+ bought in past month",
    "1K+ bought in past month",
    "2K+ bought in past month",
    "5K+ bought in past month",
    "10K+ bought in past month",
    "50+ bought in past month",
    "Flat INR 500 Off on Select Bank Cards",
    "Flat INR 1000 Off on Select Bank Cards",
    "Flat INR 250 Off on HDFC Bank Cards",
    "Flat Rs 500 Off on SBI Credit Cards",
    "Flat 10% Off on ICICI Bank Cards",
    "Extra 5% Off on Axis Bank Credit Cards",
    "Get INR 750 Off with Kotak Credit Card",
    "Additional Rs 300 Cashback on Paytm Wallet",
    "Save extra with No Cost EMI",
    "No Cost EMI available on select cards",
    "No Cost EMI starting from Rs 1500/month",
    "No Cost EMI from Rs 2000 per month",
    "EMI options available starting Rs 999/month",
    "Pay in easy EMIs with No Cost EMI",
    "Save extra with No Cost EMI on HDFC Bank",
    "100% Purchase Protection",
    "100% Genuine Products",
    "100% Secure Payment",
    "100% Authentic Products Guaranteed",
    "Certified Authentic Products",
    "All Discounts",
    "All Discounts Coupons Today's Deals",
    "All Categories",
    "All Departments",
    "Today's Deals",
    "All Offers and Deals",
    "Coupons and Offers",
    "Browse All Categories",
    "Get FREE Shipping on eligible orders shipped by Amazon",
    "Free Shipping on orders over Rs 499",
    "Free Shipping Get FREE Shipping on eligible orders",
    "Free delivery on orders above Rs 500",
    "Standard delivery available for this item",
    "Eligible for Free Delivery",
    "Delivered by Amazon",
    "Cash on delivery available",
    "Pay on delivery available",
    "Free returns within 30 days",
    "Easy returns and exchanges",
    "Hassle-free returns within 10 days",
    "Save Rs 2000 with coupon",
    "Save Rs 500 with coupon",
    "Rs 2000 off coupon applied",
    "Rs 500 off coupon applied",
    "Apply coupon to save Rs 1000",
    "Get Rs 250 off with this coupon",
    "Coupon available for this item",
    "1 new offer available",
    "2 new offers available",
    "3 offers available for this product",
    "See all available offers",
    "View all applicable offers",
    "200% Faster Ice Making in 49 Minutes",
    "300% more energy efficient",
    "500% brighter display",
    "50% more storage capacity",
    "2x faster cooling performance",
    "3x longer battery life",
    "Haier 240L 2 Star Frost Free Top Mount Double Door Refrigerator",
    "Samsung 7 KG 5 Star Fully Automatic Top Load Washing Machine",
    "LG 139 cm 55 inch QNED Mini LED 4K Ultra HD Smart TV",
    "Whirlpool 245L 3 Star Frost Free Double Door Refrigerator",
    "Bosch 7 Kg Fully Automatic Front Load Washing Machine",
    "IFB 6.5 Kg 5 Star Fully Automatic Front Loading Washing Machine",
    "4.1 out of 5 stars",
    "4.5 out of 5 stars (2345)",
    "3.8 out of 5 stars (567 ratings)",
    "Rated 4.2 out of 5",
    "837 customer ratings",
    "See all customer reviews",
    "Add to Cart",
    "Buy Now",
    "Add to Wishlist",
    "Compare with similar items",
    "See options available",
    "No featured offers available",
    "Check product availability",
    "Currently unavailable",
    "Inclusive of all taxes",
    "MRP Rs 25990",
    "Price Rs 18990",
    "You save Rs 7000 (27% off)",
    "44% off",
    "27% off MRP",
    "List price Rs 32000",
    "Deal price Rs 21999",
    "Pickup Available at nearby store",
    "Available in 3 colours",
    "Available in multiple sizes",
    "Select size to see delivery options",
    "Ships from and sold by Amazon",
    "Fulfilled by Amazon",
    "Sold by RetailNet and Fulfilled by Amazon",
    "Product specifications and features",
    "Key features of this product",
    "Technical specifications",
    "Warranty and support information",
    "1 year manufacturer warranty",
    "2 year comprehensive warranty included",
    "Energy rating 5 star BEE certified",
    "Installation charges may apply",
]

# ============================================================
# 2. MAIN PIPELINE
# ============================================================

def main():
    print("=" * 60)
    print("PHASE 2: Dataset Fix, Augmentation & EDA")
    print("=" * 60)

    # --- Load and Fix Master Dataset ---
    master_path = "../data/processed/lumichats_master_dataset.csv"
    df = pd.read_csv(master_path)
    print(f"\n📂 Loaded master dataset: {len(df)} rows")

    # Fix: NaN labels → "Benign" (not "None" — pandas reads "None" as NaN)
    nan_count = df['label'].isna().sum()
    df['label'] = df['label'].fillna('Benign')
    # Also fix any that survived as string "None"
    df.loc[df['label'] == 'None', 'label'] = 'Benign'
    print(f"✅ Fixed {nan_count} NaN labels → 'Benign'")

    # --- Add Augmented Examples ---
    print("\n📝 Adding augmented examples for rare classes...")

    aug_data = []
    for text in TRICK_QUESTIONS_EXAMPLES:
        aug_data.append({"text": text, "label": "Trick Questions"})
    for text in HIDDEN_COSTS_EXAMPLES:
        aug_data.append({"text": text, "label": "Hidden Costs"})
    for text in ROACH_MOTEL_EXAMPLES:
        aug_data.append({"text": text, "label": "Roach Motel"})
    for text in BENIGN_HARD_NEGATIVES:
        aug_data.append({"text": text, "label": "Benign"})

    aug_df = pd.DataFrame(aug_data)
    df = pd.concat([df, aug_df], ignore_index=True)

    # Deduplicate
    before = len(df)
    df = df.drop_duplicates(subset=['text'])
    print(f"   Removed {before - len(df)} duplicates after augmentation")

    # Shuffle
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Save updated master
    df.to_csv("lumichats_master_dataset_v2.csv", index=False)
    print(f"✅ Saved lumichats_master_dataset_v2.csv ({len(df)} rows)")

    # --- Label Distribution ---
    print("\n📊 Label Distribution:")
    label_counts = df['label'].value_counts()
    print(label_counts)

    # Define all 8 labels in consistent order
    ALL_LABELS = [
        "Benign", "Urgency or Scarcity", "Disguised Ads", "Misdirection",
        "Confirmshaming", "Roach Motel", "Trick Questions", "Hidden Costs"
    ]

    # ============================================================
    # 3. EDA CHARTS
    # ============================================================
    os.makedirs("charts", exist_ok=True)

    # --- Chart 1: Class Distribution ---
    fig, ax = plt.subplots(figsize=(12, 6))
    counts = [label_counts.get(l, 0) for l in ALL_LABELS]
    colors = ['#64748b', '#ef4444', '#f97316', '#eab308',
              '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899']
    bars = ax.bar(ALL_LABELS, counts, color=colors, edgecolor='white', linewidth=1.5)
    ax.set_title("Dark Pattern Category Distribution", fontsize=16, fontweight='bold', pad=15)
    ax.set_xlabel("Category", fontsize=12)
    ax.set_ylabel("Number of Examples", fontsize=12)
    ax.set_xticklabels(ALL_LABELS, rotation=35, ha='right', fontsize=10)
    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 8,
                str(count), ha='center', va='bottom', fontweight='bold', fontsize=11)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig("charts/class_distribution.png", dpi=150)
    plt.close()
    print("\n✅ Saved charts/class_distribution.png")

    # --- Chart 2: Text Length Distribution ---
    df['text_length'] = df['text'].astype(str).apply(len)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(df['text_length'], bins=50, color='#3b82f6', edgecolor='white', alpha=0.85)
    ax.set_title("Text Length Distribution", fontsize=16, fontweight='bold', pad=15)
    ax.set_xlabel("Character Length", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.axvline(df['text_length'].median(), color='#ef4444', linestyle='--',
               linewidth=2, label=f"Median: {df['text_length'].median():.0f}")
    ax.legend(fontsize=11)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    plt.savefig("charts/text_length_distribution.png", dpi=150)
    plt.close()
    print("✅ Saved charts/text_length_distribution.png")

    # --- Chart 3: Imbalance Ratio Table ---
    max_count = label_counts.max()
    imbalance = pd.DataFrame({
        "Category": ALL_LABELS,
        "Count": counts,
        "Imbalance Ratio": [f"1:{max_count // c if c > 0 else 'inf'}" for c in counts]
    })
    print("\n📊 Class Imbalance Ratios:")
    print(imbalance.to_string(index=False))

    # ============================================================
    # 4. STRATIFIED TRAIN / VAL / TEST SPLIT (70/15/15)
    # ============================================================
    print("\n✂️  Performing stratified 70/15/15 split...")

    # Drop text_length column before splitting
    df = df.drop(columns=['text_length'])

    # First split: 70% train, 30% temp
    train_df, temp_df = train_test_split(
        df, test_size=0.30, random_state=42, stratify=df['label']
    )

    # Second split: 50/50 of temp → 15% val, 15% test
    val_df, test_df = train_test_split(
        temp_df, test_size=0.50, random_state=42, stratify=temp_df['label']
    )

    train_df.to_csv("train.csv", index=False)
    val_df.to_csv("val.csv", index=False)
    test_df.to_csv("test.csv", index=False)

    print(f"   Train: {len(train_df)} rows")
    print(f"   Val:   {len(val_df)} rows")
    print(f"   Test:  {len(test_df)} rows")

    # Show split distribution
    print("\n📊 Train Label Distribution:")
    print(train_df['label'].value_counts())
    print("\n📊 Val Label Distribution:")
    print(val_df['label'].value_counts())
    print("\n📊 Test Label Distribution:")
    print(test_df['label'].value_counts())

    # Save split metadata
    split_info = {
        "total_rows": len(df),
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "labels": ALL_LABELS,
        "label_counts": {l: int(label_counts.get(l, 0)) for l in ALL_LABELS}
    }
    with open("split_info.json", "w") as f:
        json.dump(split_info, f, indent=2)

    print("\n🎉 Phase 2 Complete!")
    print("   Files created: lumichats_master_dataset_v2.csv, train.csv, val.csv, test.csv")
    print("   Charts saved in charts/ directory")


if __name__ == "__main__":
    main()
