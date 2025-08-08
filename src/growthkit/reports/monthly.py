#!/usr/bin/env python3
"""
Q3 Performance Analysis
Comprehensive analysis of 30-day sales data organized by metric tiers
"""

from datetime import datetime

import pandas as pd
import numpy as np

from growthkit.reports.file_selector import select_data_file_for_report

def load_and_clean_data():
    """Load and clean the 30-day sales data"""
    # Interactive file selection
    csv_file = select_data_file_for_report("monthly")
    if not csv_file:
        print("No file selected. Exiting.")
        return None
    
    df = pd.read_csv(csv_file)
    
    # Clean and convert numeric columns
    numeric_cols = [
        'spend',
        'cac', 'cac_1st_time',
        'roas', 'roas_1st_time',
        'aov', 'aov_1st_time',
        'ecr', 'ecr_1st_time',
        'ecpnv',
        'platformreported_cac', 'platformreported_roas',
        'new_customer_percentage', 'revenue_per_visit',
        # Added for accurate first-time calculations
        'attributed_rev_1st_time', 'transactions_1st_time',
        'visits', 'new_visits'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Fill NaN values with 0 for analysis
    df = df.fillna(0)
    
    return df

def analyze_tier_1_metrics(df):
    """Analyze Tier 1 Metrics: First-time customer performance (Accrual only)"""
    print("=" * 60)
    print("TIER 1 METRICS ANALYSIS (First-Time Customer Focus)")
    print("=" * 60)

    # Restrict to Accrual performance rows for correct attribution metrics
    accrual_df = df[df['accounting_mode'] == 'Accrual performance'].copy()

    if len(accrual_df) == 0:
        print("⚠️ No Accrual Performance data found")
        return

    # Aggregate required sums at platform level
    grouped = accrual_df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'attributed_rev_1st_time': 'sum',
        'transactions_1st_time': 'sum',
        'visits': 'sum',
        'new_visits': 'sum'
    })

    # Compute first-time metrics according to definitions
    grouped['cac_1st_time'] = (grouped['spend'] / grouped['transactions_1st_time']).replace([np.inf], 0)
    grouped['roas_1st_time'] = (grouped['attributed_rev_1st_time'] / grouped['spend']).replace([np.inf], 0)
    grouped['aov_1st_time'] = (grouped['attributed_rev_1st_time'] / grouped['transactions_1st_time']).replace([np.inf], 0)
    grouped['ecr_1st_time'] = (grouped['transactions_1st_time'] / grouped['visits']).replace([np.inf], 0)
    grouped['ecpnv'] = (grouped['spend'] / grouped['new_visits']).replace([np.inf], 0)

    platform_analysis = grouped.round(2)

    # Keep only platforms with meaningful spend
    platform_analysis = platform_analysis[platform_analysis['spend'] > 1000]
    platform_analysis = platform_analysis.sort_values('spend', ascending=False)

    print("\n🎯 TIER 1: Top Platforms by First-Time Customer Performance")
    print("-" * 70)
    if platform_analysis.empty:
        print("No platforms meet the spend threshold (>$1,000)")
    else:
        print(platform_analysis[['spend', 'cac_1st_time', 'roas_1st_time', 'aov_1st_time', 'ecr_1st_time', 'ecpnv']])

    # ---- Product campaign deep dive (unchanged) ----
    product_campaigns = accrual_df[accrual_df['campaign_name'].str.contains(
        'Red Light|PEMF|Sauna|Body Sculptor', case=False, na=False)]
    
    if len(product_campaigns) > 0:
        product_analysis = product_campaigns.groupby('campaign_name').agg({
            'spend': 'sum',
            'cac_1st_time': 'mean',
            'roas_1st_time': 'mean',
            'aov_1st_time': 'mean'
        }).round(2)
        
        product_analysis = product_analysis[product_analysis['spend'] > 100]
        product_analysis = product_analysis.sort_values('roas_1st_time', ascending=False)
        
        print("\n🏆 TIER 1: Best First-Time Customer Campaigns")
        print("-" * 45)
        print(product_analysis.head(10))
        
        # Identify winners and losers
        winners = product_analysis[product_analysis['roas_1st_time'] > 1.0]
        losers = product_analysis[product_analysis['roas_1st_time'] < 0.5]
        
        print(f"\n✅ TIER 1 WINNERS ({len(winners)} campaigns with >1.0 first-time ROAS)")
        print(f"💔 TIER 1 LOSERS ({len(losers)} campaigns with <0.5 first-time ROAS)")
        
        if len(winners) > 0:
            print("\nTop performers:")
            for campaign in winners.head(3).index:
                metrics = winners.loc[campaign]
                print(f"  • {campaign[:50]}... - ROAS: {metrics['roas_1st_time']:.2f}, CAC: ${metrics['cac_1st_time']:.0f}")

def analyze_tier_2_metrics(df):
    """Analyze Tier 2 Metrics: Overall 1-day performance"""
    print("\n\n" + "="*60)
    print("TIER 2 METRICS ANALYSIS (1-Day Attribution)")
    print("="*60)
    
    # Filter for campaigns with meaningful spend
    tier2_df = df[(df['spend'] > 0) & (df['roas'] > 0)]
    
    # Platform-level analysis
    platform_analysis = tier2_df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'cac': 'mean',
        'roas': 'mean',
        'aov': 'mean',
        'ecr': 'mean',
        'ecpnv': 'mean'
    }).round(2)
    
    platform_analysis = platform_analysis[platform_analysis['spend'] > 500]
    platform_analysis = platform_analysis.sort_values('roas', ascending=False)
    
    print("\n📊 TIER 2: Platform Performance (1-Day Attribution)")
    print("-" * 50)
    print(platform_analysis)
    
    # Calculate efficiency scores
    platform_analysis['efficiency_score'] = (platform_analysis['roas'] * 0.4 + 
                                             (1000 / platform_analysis['cac']) * 0.3 + 
                                             (platform_analysis['aov'] / 500) * 0.3)
    
    print("\n🎯 TIER 2: Platform Efficiency Ranking")
    print("-" * 35)
    efficiency_ranking = platform_analysis.sort_values('efficiency_score', ascending=False)
    for i, (platform, row) in enumerate(efficiency_ranking.head(5).iterrows(), 1):
        print(f"{i}. {platform}: Score {row['efficiency_score']:.2f} (ROAS: {row['roas']:.2f}, CAC: ${row['cac']:.0f})")
    
    # Active campaign analysis
    active_campaigns = tier2_df[tier2_df['status'] == 'Active']
    if len(active_campaigns) > 0:
        print(f"\n🔥 TIER 2: Active Campaign Performance ({len(active_campaigns)} campaigns)")
        print("-" * 45)
        
        campaign_performance = active_campaigns.groupby('campaign_name').agg({
            'spend': 'sum',
            'roas': 'mean',
            'cac': 'mean',
            'aov': 'mean'
        }).round(2)
        
        campaign_performance = campaign_performance[campaign_performance['spend'] > 200]
        campaign_performance = campaign_performance.sort_values('roas', ascending=False)
        
        print("Top 5 Active Campaigns:")
        for i, (campaign, row) in enumerate(campaign_performance.head(5).iterrows(), 1):
            print(f"{i}. {campaign[:45]}... - ROAS: {row['roas']:.2f}, Spend: ${row['spend']:.0f}")

def analyze_tier_3_metrics(df):
    """Analyze Tier 3 Metrics: Platform-reported and new customer metrics"""
    print("\n\n" + "="*60)
    print("TIER 3 METRICS ANALYSIS (Platform-Reported & New Customer)")
    print("="*60)
    
    # Filter for campaigns with platform-reported data
    tier3_df = df[(df['spend'] > 0) & 
                  ((df['platformreported_roas'] > 0) | (df['new_customer_percentage'] > 0))]
    
    # Platform-reported vs actual performance
    platform_comparison = tier3_df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'platformreported_cac': 'mean',
        'cac': 'mean',
        'platformreported_roas': 'mean',
        'roas': 'mean',
        'new_customer_percentage': 'mean',
        'revenue_per_visit': 'mean'
    }).round(2)
    
    platform_comparison = platform_comparison[platform_comparison['spend'] > 500]
    
    print("\n📈 TIER 3: Platform-Reported vs Actual Performance")
    print("-" * 50)
    
    # Calculate discrepancies
    platform_comparison['roas_discrepancy'] = (platform_comparison['platformreported_roas'] - 
                                              platform_comparison['roas'])
    platform_comparison['cac_discrepancy'] = (platform_comparison['platformreported_cac'] - 
                                             platform_comparison['cac'])
    
    print(platform_comparison[['spend', 'platformreported_roas', 'roas', 'roas_discrepancy', 
                              'new_customer_percentage', 'revenue_per_visit']])
    
    # New customer acquisition analysis
    new_customer_analysis = tier3_df[tier3_df['new_customer_percentage'] > 0]
    if len(new_customer_analysis) > 0:
        print(f"\n👥 TIER 3: New Customer Acquisition ({len(new_customer_analysis)} campaigns)")
        print("-" * 45)
        
        nc_performance = new_customer_analysis.groupby('breakdown_platform_northbeam').agg({
            'spend': 'sum',
            'new_customer_percentage': 'mean',
            'revenue_per_visit': 'mean',
            'roas': 'mean'
        }).round(2)
        
        nc_performance = nc_performance[nc_performance['spend'] > 200]
        nc_performance = nc_performance.sort_values('new_customer_percentage', ascending=False)
        
        print("Platform New Customer Performance:")
        for platform, row in nc_performance.iterrows():
            print(f"  • {platform}: {row['new_customer_percentage']:.0f}% new customers, "
                  f"${row['revenue_per_visit']:.2f} RPV, {row['roas']:.2f} ROAS")

def generate_strategic_recommendations(df):
    """Generate strategic recommendations based on the analysis"""
    print("\n\n" + "="*60)
    print("STRATEGIC RECOMMENDATIONS FOR INGRID")
    print("="*60)
    
    # Platform efficiency analysis
    platform_summary = df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'roas': 'mean',
        'cac': 'mean',
        'aov': 'mean'
    }).round(2)
    
    platform_summary = platform_summary[platform_summary['spend'] > 1000]
    platform_summary = platform_summary.sort_values('roas', ascending=False)
    
    print("\n🎯 RECOMMENDATION 1: Platform Optimization")
    print("-" * 40)
    
    # Identify top and bottom performers
    top_platforms = platform_summary.head(3)
    bottom_platforms = platform_summary.tail(3)
    
    print("✅ SCALE THESE PLATFORMS:")
    for platform, row in top_platforms.iterrows():
        print(f"  • {platform}: {row['roas']:.2f} ROAS, ${row['spend']:.0f} spend")
    
    print("\n❌ REDUCE/OPTIMIZE THESE PLATFORMS:")
    for platform, row in bottom_platforms.iterrows():
        print(f"  • {platform}: {row['roas']:.2f} ROAS, ${row['spend']:.0f} spend")
    
    # Product campaign analysis
    product_campaigns = df[df['campaign_name'].str.contains(
        'Red Light|PEMF|Sauna|Body Sculptor', case=False, na=False)]
    
    if len(product_campaigns) > 0:
        product_performance = product_campaigns.groupby('campaign_name').agg({
            'spend': 'sum',
            'roas': 'mean',
            'cac': 'mean',
            'aov': 'mean'
        }).round(2)
        
        product_performance = product_performance[product_performance['spend'] > 100]
        product_performance = product_performance.sort_values('roas', ascending=False)
        
        print("\n🏆 RECOMMENDATION 2: Product Campaign Focus")
        print("-" * 42)
        
        winners = product_performance[product_performance['roas'] > 1.0]
        losers = product_performance[product_performance['roas'] < 0.5]
        
        print(f"✅ DOUBLE DOWN ON WINNERS ({len(winners)} campaigns):")
        for campaign in winners.head(3).index:
            metrics = winners.loc[campaign]
            print(f"  • {campaign[:40]}... - ROAS: {metrics['roas']:.2f}")
        
        print(f"\n❌ PAUSE/OPTIMIZE LOSERS ({len(losers)} campaigns):")
        for campaign in losers.head(3).index:
            metrics = losers.loc[campaign]
            print(f"  • {campaign[:40]}... - ROAS: {metrics['roas']:.2f}")
    
    # Budget reallocation calculation
    total_spend = df['spend'].sum()
    inefficient_spend = df[df['roas'] < 0.5]['spend'].sum()
    
    print("\n💰 RECOMMENDATION 3: Budget Reallocation")
    print("-" * 42)
    print(f"Total 30-day spend: ${total_spend:,.0f}")
    print(f"Inefficient spend (ROAS < 0.5): ${inefficient_spend:,.0f}")
    print(f"Potential savings: ${inefficient_spend:,.0f} ({inefficient_spend/total_spend*100:.1f}%)")
    
    # Revenue impact projection
    avg_winner_roas = platform_summary[platform_summary['roas'] > 1.5]['roas'].mean()
    projected_revenue_lift = inefficient_spend * avg_winner_roas
    
    print(f"\nIf reallocated to winning platforms/campaigns:")
    print(f"  • Projected revenue lift: ${projected_revenue_lift:,.0f}")
    print(f"  • Potential ROAS improvement: {avg_winner_roas:.2f}x")
    
    print("\n🎯 IMMEDIATE ACTION ITEMS:")
    print("1. Pause campaigns with ROAS < 0.5 within 48 hours")
    print("2. Reallocate budget to top 3 performing platforms")
    print("3. Scale Red Light Hat campaigns based on strong performance")
    print("4. Investigate Meta performance decline (CVR down 52%)")
    print("5. Test new creative angles for PEMF and Sauna campaigns")

def main():
    """Main analysis function"""
    print("Eskiin Q3 Performance Analysis")
    print("Data Period: Last 30 Days")
    print("Analysis Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Load data
    df = load_and_clean_data()
    if df is None:
        return
    print(f"\nDataset loaded: {len(df)} campaigns analyzed")
    
    # Run tier analyses
    analyze_tier_1_metrics(df)
    analyze_tier_2_metrics(df)
    analyze_tier_3_metrics(df)
    
    # Generate recommendations
    generate_strategic_recommendations(df)
    
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE - Ready for Leadership Review")
    print("="*60)

if __name__ == "__main__":
    main() 