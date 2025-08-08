"""Canonical product and alias metadata for GrowthKit report modules.

This file is GENERATED once from docs/product-list.md then maintained manually.
It must contain *data only* (no heavy imports or runtime code) so that any
other module can safely `import growthkit.reports.product_data` without side-effects.
"""

from __future__ import annotations
from typing import Dict, List

# ---------------------------------------------------------------------------
# Product summaries – not currently used by analysis but kept for reference
# ---------------------------------------------------------------------------
SUMMARIES: Dict[str, str] = {
    "Microcurrent Body Sculptor Ritual Set": "Handheld microcurrent device with red & near-infrared LEDs plus activator gel and magnesium spray to sculpt fascia, boost lymph flow, relieve muscles, and firm skin.",
    "Red Light Hat": "650 nm red-light cap boosts scalp circulation to strengthen follicles, reduce shedding, and encourage thicker hair with 10-minute daily use.",
    "Infrared Sauna Blanket": "Portable far-infrared blanket (up to ~175 °F) with crystal & charcoal layers for deep detox, calorie burn, stress relief, and post-sweat glow.",
    "Red Light Face Mask": "FDA-cleared mask combining red & near-infrared LEDs to stimulate collagen, calm redness, fight acne, and brighten skin in hands-free sessions.",
    "Red Light Neck Enhancer": "Flexible neck/décolletage panel delivering red/NIR light that firms skin, fades lines, and extends facial light-therapy benefits.",
    "Infrared PEMF Pro Mat": "Full-size mat layering far-infrared heat, PEMF, negative ions, and crystals to ease pain, speed recovery, and promote deep relaxation.",
    "Infrared PEMF Go Mat": "Travel-ready version of the Pro Mat offering Infrared + PEMF therapy in a compact foldable pad for on-the-go relief.",
    "Full Spectrum Infrared Sauna": "Clearlight wooden cabin with low-EMF heaters providing near, mid & far infrared plus chromotherapy and audio for spa-level detox.",
    "Sauna Blanket Starter Kit": "Sauna Blanket bundled with organic-cotton towel insert and backpack for cleaner, more comfortable, portable sweat sessions.",
    "PEMF Pro Mat Starter Kit": "Pro Mat packaged with cotton cover and cleaner for an all-in-one recovery and hygiene setup.",
    "Red Light Starter Kit": "Bundle of Red Light Face Mask, Red Light Hat, and Glow Serum for skin renewal, hair growth, and whole-body radiance.",
    "Summer Body Recover & Sculpt": "Microcurrent Body Sculptor, SweatBand, and High-Dration Powder trio to tone, sweat smarter, and replenish electrolytes.",
    "Summer Travel Glow Kit": "Four transformative travel-size essentials to restore hydration, protect energy, and keep skin glowing on the go.",
    "Best Seller Bundle": "High-value pair of Infrared Sauna Blanket and Infrared PEMF Mat for weekly detox sweats and grounding recovery.",
    "Turn Me On Kit": "Circulation-boosting collection designed to lower cortisol, melt tension, and spark vitality for enhanced pleasure.",
    "PEMF Go Mat Starter Kit": "Go Mat plus organic cover/cleaner for instant, portable Infrared + PEMF recovery.",
    "Endorphin Kit": "Sweat-amplifying Endorphin Oil and SweatBand set (with fanny pack) to raise core heat, detox, and fuel workout endorphins.",
    "Oxytocin Kit": "Dry brush, Oxytocin Oil, and self-care tools that exfoliate, nourish, and foster a feel-good connection through the 'love hormone'.",
    "The Supermom Bundle": "Quick-ritual kit (incl. Red Light Face Mask) giving multitasking parents daily glow and relaxation without rescheduling.",
    "The Sweat it Out Bundle": "Endorphin Oil, SweatBand, and Sauna Blanket combo for intensified detox and endorphin-boosting sweat sessions.",
    "After Bedtime Bundle": "Copper Dry Brush, Oxytocin Oil, and Serotonin Soak salts create a three-step nighttime ritual to exfoliate, nourish, and deeply relax.",
    "Supercharge Copper Body Brush": "Ion-charged copper bristles exfoliate, stimulate lymph drainage, balance EMFs, and energize skin for a radiant glow.",
    "SweatBand": "Neoprene waist band supports core, locks in heat, and enhances workouts or sauna sessions when paired with oils.",
    "EMF Blocking Fanny Pack": "Vegan-leather waist bag lined with silver fabric to shield against EMFs while keeping phone and essentials secure during activity.",
    "Infrared Sauna Blanket Insert": "Absorbent GOTS-certified organic-cotton towel liner that keeps sauna blanket clean and comfortable.",
    "High Maintenance Cleaner": "Probiotic, essential-oil all-purpose spray that safely cleans wellness tech and surfaces without harsh chemicals.",
    "Eskiin Time-Marked Glass Water Bottle": "Heat-safe glass bottle with hourly markers to encourage chemical-free hydration before and after sweat sessions.",
    "Sauna Blanket Bag": "Backpack-style carrier sized for folded Sauna Blanket, towel insert, and cleaner for easy transport.",
    "PEMF Mat Cover": "Organic-cotton cushioned cover that protects PEMF Mat, adds comfort, and simplifies cleanup between users.",
    "100% Organic Cotton Bath Robe": "Plush, breathable GOTS-certified cotton robe with deep pockets—perfect for post-sauna lounging or spa-day comfort.",
    "Detox Drops": "Liquid chlorophyll formula binds toxins, boosts immunity, and supports skin radiance for gentle daily detox.",
    "High-Dration Powder": "Sugar-free electrolyte blend with watermelon, coconut water, magnesium, and vitamins to replace minerals lost in sweat.",
    "HighDration Kit": "Time-Marked Water Bottle plus a 7-day supply of High-Dration Powder for effortless hydration tracking.",
    "Transdermal Magnesium Spray": "Pure Zechstein magnesium spray absorbs through skin to relieve muscles, calm nerves, and improve sleep—ideal post-sweat.",
    "Endorphin Oil": "Heat-activated castor oil blend with magnesium and warming botanicals to amplify sweat, soothe soreness, and raise body temperature.",
    "Serotonin Soak Salt": "Magnesium-rich bath salts with apple cider vinegar and algae to relax muscles, detoxify, and elevate mood.",
    "Light-Activated Glow Serum": "Bio-nutrient serum formulated to amplify red-light treatments, plumping and hydrating skin for amplified radiance.",
    "Oxytocin Oil": "Botanical body oil that pairs with dry brushing to deeply nourish skin, boost elasticity, and evoke sensual relaxation.",
    "Daily Dose Ritual": "Two-step routine—Copper Dry Brush plus Oxytocin Oil—for daily circulation boost, exfoliation, and luminous skin.",
    "Sculpting Activator Gel": "Conductive, nutrient-rich gel that enhances microcurrent efficacy while firming, smoothing, and hydrating skin.",
    "eGift Card": "Digital gift card in multiple denominations allowing recipients to choose their preferred Eskiin wellness products."
}

# ---------------------------------------------------------------------------
# Category membership – product → category string
# ---------------------------------------------------------------------------
PRODUCT_TO_CATEGORY: Dict[str, str] = {
    # Wellness Tech
    "Microcurrent Body Sculptor Ritual Set": "Wellness Tech",
    "Red Light Hat": "Wellness Tech",
    "Infrared Sauna Blanket": "Wellness Tech",
    "Red Light Face Mask": "Wellness Tech",
    "Red Light Neck Enhancer": "Wellness Tech",
    "Infrared PEMF Pro Mat": "Wellness Tech",
    "Infrared PEMF Go Mat": "Wellness Tech",
    "Full Spectrum Infrared Sauna": "Wellness Tech",

    # Bundle & Save
    "Sauna Blanket Starter Kit": "Bundle & Save",
    "PEMF Pro Mat Starter Kit": "Bundle & Save",
    "Red Light Starter Kit": "Bundle & Save",
    "Summer Body Recover & Sculpt": "Bundle & Save",
    "Summer Travel Glow Kit": "Bundle & Save",
    "Best Seller Bundle": "Bundle & Save",
    "Turn Me On Kit": "Bundle & Save",
    "PEMF Go Mat Starter Kit": "Bundle & Save",
    "Endorphin Kit": "Bundle & Save",
    "Oxytocin Kit": "Bundle & Save",
    "The Supermom Bundle": "Bundle & Save",
    "The Sweat it Out Bundle": "Bundle & Save",
    "After Bedtime Bundle": "Bundle & Save",

    # Accessories
    "Supercharge Copper Body Brush": "Accessories",
    "SweatBand": "Accessories",
    "EMF Blocking Fanny Pack": "Accessories",
    "Infrared Sauna Blanket Insert": "Accessories",
    "High Maintenance Cleaner": "Accessories",
    "Eskiin Time-Marked Glass Water Bottle": "Accessories",
    "Sauna Blanket Bag": "Accessories",
    "PEMF Mat Cover": "Accessories",
    "100% Organic Cotton Bath Robe": "Accessories",

    # Supplements
    "Detox Drops": "Supplements",
    "High-Dration Powder": "Supplements",
    "HighDration Kit": "Supplements",

    # Body Care
    "Transdermal Magnesium Spray": "Body Care",
    "Endorphin Oil": "Body Care",
    "Serotonin Soak Salt": "Body Care",
    "Light-Activated Glow Serum": "Body Care",
    "Oxytocin Oil": "Body Care",
    "Daily Dose Ritual": "Body Care",
    "Sculpting Activator Gel": "Body Care",

    # Gifting
    "eGift Card": "Gifting",
}

# ---------------------------------------------------------------------------
# Aliases – any lower-cased keyword / phrase → canonical product name
# ---------------------------------------------------------------------------
ALIASES: Dict[str, str] = {
    # Map common abbreviations or alternate spellings to canonical product names
    # These can be updated over time as new naming conventions appear in ad accounts
    "sauna blanket": "Infrared Sauna Blanket",
    "sauna blanket starter kit": "Sauna Blanket Starter Kit",
    "pemf mat": "Infrared PEMF Pro Mat",
    "pemf pro mat": "Infrared PEMF Pro Mat",
    "pemf go mat": "Infrared PEMF Go Mat",
    "red light mask": "Red Light Face Mask",
    "red light face mask": "Red Light Face Mask",
    "red light hat": "Red Light Hat",
    "neck enhancer": "Red Light Neck Enhancer",
    "microcurrent body sculptor": "Microcurrent Body Sculptor Ritual Set",
    "body sculptor": "Microcurrent Body Sculptor Ritual Set",
    "body sculptor ritual set": "Microcurrent Body Sculptor Ritual Set",
    "sculptor": "Microcurrent Body Sculptor Ritual Set",
    "body sculpt": "Microcurrent Body Sculptor Ritual Set",

    # PEMF Pro Mat variants
    "pemfpro": "Infrared PEMF Pro Mat",
    "pemfpromat": "Infrared PEMF Pro Mat",

    # Recovery / Solution bundles (map to Best Seller Bundle)
    "solution recovery": "Best Seller Bundle",
    "recovery bundle": "Best Seller Bundle",

    # Serotonin Soak misspelling
    "seratonin soak": "Serotonin Soak Salt",

    # Red Light Face Mask variants
    "redlightfacemask": "Red Light Face Mask",
    "red light facemask": "Red Light Face Mask",
    "magnewsium spray": "Transdermal Magnesium Spray",
    "magnesiumspray": "Transdermal Magnesium Spray",

    # Additional aliases from latest unattributed review
    "red light neck": "Red Light Neck Enhancer",
    "redlightneck": "Red Light Neck Enhancer",
    "rlne": "Red Light Neck Enhancer",

    "infrared sauna": "Full Spectrum Infrared Sauna",
    "infraredsauna": "Full Spectrum Infrared Sauna",
    "full spectrum sauna": "Full Spectrum Infrared Sauna",
    "fullspectrumsauna": "Full Spectrum Infrared Sauna",

    "saunblanket": "Infrared Sauna Blanket",
    "sauna body wrap": "Infrared Sauna Blanket",
    "saunabodywrap": "Infrared Sauna Blanket",

    "soak salt": "Serotonin Soak Salt",
    "soaksalt": "Serotonin Soak Salt",

    "glow serum": "Light-Activated Glow Serum",
    "glowserum": "Light-Activated Glow Serum",

    "pemfgo": "Infrared PEMF Go Mat",
    # Generic short forms
    "pemf": "Infrared PEMF Pro Mat",
    "redlight": "Red Light Face Mask",
    "red light": "Red Light Face Mask",
    "blanket": "Infrared Sauna Blanket",

    # High-confidence tokens from latest unattributed scan
    "sculpt": "Microcurrent Body Sculptor Ritual Set",
    "sculptpdp": "Microcurrent Body Sculptor Ritual Set",

    # Mask variants
    "mask": "Red Light Face Mask",
    "masks": "Red Light Face Mask",
    "led mask": "Red Light Face Mask",
    "ledmask": "Red Light Face Mask",
    "led masks": "Red Light Face Mask",
    "ledmasks": "Red Light Face Mask",
    "face mask": "Red Light Face Mask",
    "facemask": "Red Light Face Mask",

    # Soak shorthand
    "soak": "Serotonin Soak Salt",

    # Mat shorthand
    "mat": "Infrared PEMF Pro Mat",
    "dose mat": "Infrared PEMF Pro Mat",

    # Medium-confidence tokens
    "brush": "Supercharge Copper Body Brush",
    "serum": "Light-Activated Glow Serum",
    "towel": "Infrared Sauna Blanket Insert",
    "insert": "Infrared Sauna Blanket Insert",
    "cleaner": "High Maintenance Cleaner",
}

# Convenience: longest-first list for greedy matching
ALIAS_SORTED: List[tuple[str, str]] = sorted(ALIASES.items(), key=lambda kv: -len(kv[0]))

__all__ = [
    "SUMMARIES",
    "PRODUCT_TO_CATEGORY",
    "ALIASES",
    "ALIAS_SORTED",
]
