# Taxonomy version. Bump on every edit affecting slugs, labels, or parent assignments.
# Format: YYYY-MM-DD-N (N is the daily revision counter, starting at 1).
TAXONOMY_VERSION = '2026-05-15-2'

# Parent categories. 18 entries. Used only for aggregation (clustering rollups,
# dashboard summaries). The extractor never returns a parent slug as topic_id.
# Translations land in Task 14 — labels dict starts empty.
PARENTS = [
    {'slug': 'governance', 'label_en': 'Governance & Institutions', 'labels': {}},
    {'slug': 'participation', 'label_en': 'Participation & Deliberation', 'labels': {}},
    {'slug': 'economic_fiscal', 'label_en': 'Economic & Fiscal Policy', 'labels': {}},
    {'slug': 'social', 'label_en': 'Social Policy & Welfare', 'labels': {}},
    {'slug': 'health', 'label_en': 'Health & Welfare', 'labels': {}},
    {'slug': 'education', 'label_en': 'Education', 'labels': {}},
    {'slug': 'justice_rights', 'label_en': 'Justice & Rights', 'labels': {}},
    {'slug': 'environment', 'label_en': 'Environment & Climate', 'labels': {}},
    {'slug': 'energy', 'label_en': 'Energy & Resources', 'labels': {}},
    {'slug': 'transport', 'label_en': 'Transportation & Mobility', 'labels': {}},
    {'slug': 'housing_urban', 'label_en': 'Housing & Urban Development', 'labels': {}},
    {'slug': 'agriculture_rural', 'label_en': 'Agriculture & Rural Development', 'labels': {}},
    {'slug': 'technology', 'label_en': 'Technology & Digital', 'labels': {}},
    {'slug': 'media_information', 'label_en': 'Media & Information', 'labels': {}},
    {'slug': 'culture_heritage', 'label_en': 'Culture & Heritage', 'labels': {}},
    {'slug': 'migration', 'label_en': 'Migration & Integration', 'labels': {}},
    {'slug': 'public_safety', 'label_en': 'Public Safety & Security', 'labels': {}},
    {'slug': 'foreign_affairs', 'label_en': 'Foreign Affairs & International', 'labels': {}},
]

# Leaf topics. 91 entries. What the extractor matches against and what
# ArticleTopic.normalized stores. Every leaf must reference a parent slug.
# Translations land in Task 14 — labels dict starts empty.
LEAVES = [
    # --- governance ---
    {'slug': 'accountability', 'label_en': 'Accountability', 'parent': 'governance', 'labels': {}},
    {'slug': 'anti_corruption', 'label_en': 'Anti-Corruption', 'parent': 'governance', 'labels': {}},
    {'slug': 'electoral_systems', 'label_en': 'Electoral Systems', 'parent': 'governance', 'labels': {}},
    {'slug': 'government_transparency', 'label_en': 'Government Transparency', 'parent': 'governance', 'labels': {}},
    {'slug': 'institutional_trust', 'label_en': 'Institutional Trust', 'parent': 'governance', 'labels': {}},
    {'slug': 'local_governance', 'label_en': 'Local Governance', 'parent': 'governance', 'labels': {}},
    {'slug': 'public_procurement', 'label_en': 'Public Procurement', 'parent': 'governance', 'labels': {}},
    {'slug': 'regional_policy', 'label_en': 'Regional & Territorial Policy', 'parent': 'governance', 'labels': {}},
    {'slug': 'rule_of_law', 'label_en': 'Rule of Law', 'parent': 'governance', 'labels': {}},
    {'slug': 'voting_and_elections', 'label_en': 'Voting and Elections', 'parent': 'governance', 'labels': {}},
    # --- participation ---
    {'slug': 'citizen_assemblies', 'label_en': 'Citizen Assemblies', 'parent': 'participation', 'labels': {}},
    {'slug': 'citizen_participation', 'label_en': 'Civic Participation', 'parent': 'participation', 'labels': {}},
    {'slug': 'e_participation', 'label_en': 'E-Participation & Digital Engagement', 'parent': 'participation', 'labels': {}},
    {'slug': 'public_consultation', 'label_en': 'Public Consultation', 'parent': 'participation', 'labels': {}},
    # --- economic_fiscal ---
    {'slug': 'consumer_protection', 'label_en': 'Consumer Protection', 'parent': 'economic_fiscal', 'labels': {}},
    {'slug': 'economic_policy', 'label_en': 'Economic Policy', 'parent': 'economic_fiscal', 'labels': {}},
    {'slug': 'labour_and_employment', 'label_en': 'Labour and Employment', 'parent': 'economic_fiscal', 'labels': {}},
    {'slug': 'labour_relations', 'label_en': 'Labour Relations & Trade Unions', 'parent': 'economic_fiscal', 'labels': {}},
    {'slug': 'public_finance', 'label_en': 'Public Finance', 'parent': 'economic_fiscal', 'labels': {}},
    {'slug': 'taxation', 'label_en': 'Taxation', 'parent': 'economic_fiscal', 'labels': {}},
    # --- social ---
    {'slug': 'companion_animals', 'label_en': 'Companion Animals', 'parent': 'social', 'labels': {}},
    {'slug': 'inequality', 'label_en': 'Inequality', 'parent': 'social', 'labels': {}},
    {'slug': 'intergenerational_justice', 'label_en': 'Intergenerational Justice', 'parent': 'social', 'labels': {}},
    {'slug': 'pensions', 'label_en': 'Pensions & Social Insurance', 'parent': 'social', 'labels': {}},
    {'slug': 'social_cohesion', 'label_en': 'Social Cohesion', 'parent': 'social', 'labels': {}},
    {'slug': 'social_justice', 'label_en': 'Social Justice', 'parent': 'social', 'labels': {}},
    {'slug': 'social_welfare', 'label_en': 'Social Welfare & Benefits', 'parent': 'social', 'labels': {}},
    {'slug': 'youth_policy', 'label_en': 'Youth Policy', 'parent': 'social', 'labels': {}},
    # --- health ---
    {'slug': 'healthcare_policy', 'label_en': 'Healthcare Policy', 'parent': 'health', 'labels': {}},
    {'slug': 'long_term_care', 'label_en': 'Long-Term Care', 'parent': 'health', 'labels': {}},
    {'slug': 'mental_health', 'label_en': 'Mental Health', 'parent': 'health', 'labels': {}},
    {'slug': 'public_health', 'label_en': 'Public Health', 'parent': 'health', 'labels': {}},
    # --- education ---
    {'slug': 'early_childhood_education', 'label_en': 'Early Childhood Education', 'parent': 'education', 'labels': {}},
    {'slug': 'education_funding', 'label_en': 'Education Funding', 'parent': 'education', 'labels': {}},
    {'slug': 'education_policy', 'label_en': 'Education Policy', 'parent': 'education', 'labels': {}},
    {'slug': 'higher_education', 'label_en': 'Higher Education', 'parent': 'education', 'labels': {}},
    {'slug': 'teacher_staffing', 'label_en': 'Teacher Staffing & Pay', 'parent': 'education', 'labels': {}},
    {'slug': 'vocational_education', 'label_en': 'Vocational Education & Training', 'parent': 'education', 'labels': {}},
    # --- justice_rights ---
    {'slug': 'accessibility', 'label_en': 'Accessibility', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'child_welfare', 'label_en': 'Child Welfare & Protection', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'civil_liberties', 'label_en': 'Civil Liberties', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'disability_rights', 'label_en': 'Disability Rights & Access', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'freedom_of_expression', 'label_en': 'Freedom of Expression', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'gender_equality', 'label_en': 'Gender Equality', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'human_rights', 'label_en': 'Human Rights', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'judicial_reform', 'label_en': 'Judicial Reform', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'minority_rights', 'label_en': 'Minority Rights', 'parent': 'justice_rights', 'labels': {}},
    {'slug': 'police_reform', 'label_en': 'Police Reform & Accountability', 'parent': 'justice_rights', 'labels': {}},
    # --- environment ---
    {'slug': 'biodiversity', 'label_en': 'Biodiversity & Nature Protection', 'parent': 'environment', 'labels': {}},
    {'slug': 'climate_adaptation', 'label_en': 'Climate Adaptation', 'parent': 'environment', 'labels': {}},
    {'slug': 'climate_change', 'label_en': 'Climate Change', 'parent': 'environment', 'labels': {}},
    {'slug': 'environmental_policy', 'label_en': 'Environmental Policy', 'parent': 'environment', 'labels': {}},
    {'slug': 'waste_management', 'label_en': 'Waste Management & Circular Economy', 'parent': 'environment', 'labels': {}},
    {'slug': 'water_management', 'label_en': 'Water Management', 'parent': 'environment', 'labels': {}},
    {'slug': 'wildlife_protection', 'label_en': 'Wildlife Protection', 'parent': 'environment', 'labels': {}},
    # --- energy ---
    {'slug': 'energy_poverty', 'label_en': 'Energy Poverty', 'parent': 'energy', 'labels': {}},
    {'slug': 'energy_transition', 'label_en': 'Energy Transition', 'parent': 'energy', 'labels': {}},
    {'slug': 'renewable_energy', 'label_en': 'Renewable Energy', 'parent': 'energy', 'labels': {}},
    # --- transport ---
    {'slug': 'public_transport', 'label_en': 'Public Transport', 'parent': 'transport', 'labels': {}},
    {'slug': 'road_infrastructure', 'label_en': 'Road Infrastructure', 'parent': 'transport', 'labels': {}},
    {'slug': 'transportation', 'label_en': 'Transportation', 'parent': 'transport', 'labels': {}},
    # --- housing_urban ---
    {'slug': 'housing', 'label_en': 'Housing', 'parent': 'housing_urban', 'labels': {}},
    {'slug': 'housing_affordability', 'label_en': 'Housing Affordability', 'parent': 'housing_urban', 'labels': {}},
    {'slug': 'land_use', 'label_en': 'Land Use & Planning', 'parent': 'housing_urban', 'labels': {}},
    {'slug': 'urban_development', 'label_en': 'Urban Development', 'parent': 'housing_urban', 'labels': {}},
    # --- agriculture_rural ---
    {'slug': 'agriculture', 'label_en': 'Agricultural Policy', 'parent': 'agriculture_rural', 'labels': {}},
    {'slug': 'food_safety', 'label_en': 'Food Safety', 'parent': 'agriculture_rural', 'labels': {}},
    {'slug': 'livestock_welfare', 'label_en': 'Livestock Welfare', 'parent': 'agriculture_rural', 'labels': {}},
    {'slug': 'rural_development', 'label_en': 'Rural Development', 'parent': 'agriculture_rural', 'labels': {}},
    # --- technology ---
    {'slug': 'algorithmic_decision_making', 'label_en': 'Algorithmic Decision Making', 'parent': 'technology', 'labels': {}},
    {'slug': 'artificial_intelligence', 'label_en': 'Artificial Intelligence', 'parent': 'technology', 'labels': {}},
    {'slug': 'automation', 'label_en': 'Automation', 'parent': 'technology', 'labels': {}},
    {'slug': 'bias_and_fairness', 'label_en': 'Bias and Fairness', 'parent': 'technology', 'labels': {}},
    {'slug': 'cybersecurity', 'label_en': 'Cybersecurity', 'parent': 'technology', 'labels': {}},
    {'slug': 'data_governance', 'label_en': 'Data Governance', 'parent': 'technology', 'labels': {}},
    {'slug': 'digital_inclusion', 'label_en': 'Digital Inclusion', 'parent': 'technology', 'labels': {}},
    {'slug': 'digital_platforms', 'label_en': 'Digital Platforms', 'parent': 'technology', 'labels': {}},
    {'slug': 'privacy_and_data_protection', 'label_en': 'Privacy and Data Protection', 'parent': 'technology', 'labels': {}},
    {'slug': 'surveillance_technologies', 'label_en': 'Surveillance Technologies', 'parent': 'technology', 'labels': {}},
    # --- media_information ---
    {'slug': 'media_education', 'label_en': 'Media & Digital Literacy', 'parent': 'media_information', 'labels': {}},
    {'slug': 'media_regulation', 'label_en': 'Media Regulation', 'parent': 'media_information', 'labels': {}},
    {'slug': 'misinformation', 'label_en': 'Misinformation', 'parent': 'media_information', 'labels': {}},
    {'slug': 'platform_regulation', 'label_en': 'Platform & Online Services Regulation', 'parent': 'media_information', 'labels': {}},
    # --- culture_heritage ---
    {'slug': 'cultural_heritage', 'label_en': 'Cultural Heritage', 'parent': 'culture_heritage', 'labels': {}},
    {'slug': 'cultural_policy', 'label_en': 'Cultural Policy', 'parent': 'culture_heritage', 'labels': {}},
    {'slug': 'language_policy', 'label_en': 'Language & Minority Language Policy', 'parent': 'culture_heritage', 'labels': {}},
    {'slug': 'sports_policy', 'label_en': 'Sports & Physical Activity Policy', 'parent': 'culture_heritage', 'labels': {}},
    # --- migration ---
    {'slug': 'migration_policy', 'label_en': 'Migration Policy', 'parent': 'migration', 'labels': {}},
    {'slug': 'refugee_integration', 'label_en': 'Refugee & Asylum Policy', 'parent': 'migration', 'labels': {}},
    # --- public_safety (empty in this phase — no leaves) ---
    # --- foreign_affairs ---
    {'slug': 'defence', 'label_en': 'Defence & Security Policy', 'parent': 'foreign_affairs', 'labels': {}},
    {'slug': 'eu_affairs', 'label_en': 'EU Affairs & European Integration', 'parent': 'foreign_affairs', 'labels': {}},
]

# Backward-compat shim. Some legacy code paths and tests still import INITIAL_TOPICS.
# Compose it from LEAVES so nothing breaks until those call sites are migrated
# (seed_taxonomy refactor is Task 7).
INITIAL_TOPICS = [(leaf['slug'], leaf['label_en']) for leaf in LEAVES]
