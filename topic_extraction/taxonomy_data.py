# Taxonomy version. Bump on every edit affecting slugs, labels, or parent assignments.
# Format: YYYY-MM-DD-N (N is the daily revision counter, starting at 1).
TAXONOMY_VERSION = '2026-05-20-1'

# Parent categories. 18 entries. Used only for aggregation (clustering rollups,
# dashboard summaries). The extractor never returns a parent slug as topic_id.
# labels carries Greek (el) only; German (de) deferred to Task 14b. Source: docs/superpowers/taxonomy-translations-draft.md
PARENTS = [
    {'slug': 'governance', 'label_en': 'Governance & Institutions', 'labels': {'el': 'Διακυβέρνηση & Θεσμοί'}},
    {'slug': 'participation', 'label_en': 'Participation & Deliberation', 'labels': {'el': 'Συμμετοχή & Διαβούλευση'}},
    {'slug': 'economic_fiscal', 'label_en': 'Economic & Fiscal Policy', 'labels': {'el': 'Οικονομική & Δημοσιονομική Πολιτική'}},
    {'slug': 'social', 'label_en': 'Social Policy & Welfare', 'labels': {'el': 'Κοινωνική Πολιτική & Πρόνοια'}},
    {'slug': 'health', 'label_en': 'Health & Welfare', 'labels': {'el': 'Υγεία & Υγειονομική Περίθαλψη'}},
    {'slug': 'education', 'label_en': 'Education', 'labels': {'el': 'Εκπαίδευση'}},
    {'slug': 'justice_rights', 'label_en': 'Justice & Rights', 'labels': {'el': 'Δικαιοσύνη & Δικαιώματα'}},
    {'slug': 'environment', 'label_en': 'Environment & Climate', 'labels': {'el': 'Περιβάλλον & Κλίμα'}},
    {'slug': 'energy', 'label_en': 'Energy & Resources', 'labels': {'el': 'Ενέργεια & Πόροι'}},
    {'slug': 'transport', 'label_en': 'Transportation & Mobility', 'labels': {'el': 'Μεταφορές & Κινητικότητα'}},
    {'slug': 'housing_urban', 'label_en': 'Housing & Urban Development', 'labels': {'el': 'Στέγαση & Αστική Ανάπτυξη'}},
    {'slug': 'agriculture_rural', 'label_en': 'Agriculture & Rural Development', 'labels': {'el': 'Γεωργία & Αγροτική Ανάπτυξη'}},
    {'slug': 'technology', 'label_en': 'Technology & Digital', 'labels': {'el': 'Τεχνολογία & Ψηφιακή Πολιτική'}},
    {'slug': 'media_information', 'label_en': 'Media & Information', 'labels': {'el': 'Μέσα Ενημέρωσης & Πληροφορία'}},
    {'slug': 'culture_heritage', 'label_en': 'Culture & Heritage', 'labels': {'el': 'Πολιτισμός & Πολιτιστική Κληρονομιά'}},
    {'slug': 'migration', 'label_en': 'Migration & Integration', 'labels': {'el': 'Μετανάστευση & Ένταξη'}},
    {'slug': 'public_safety', 'label_en': 'Public Safety & Security', 'labels': {'el': 'Δημόσια Ασφάλεια & Τάξη'}},
    {'slug': 'foreign_affairs', 'label_en': 'Foreign Affairs & International', 'labels': {'el': 'Εξωτερικές Υποθέσεις & Διεθνείς Σχέσεις'}},
]

# Leaf topics. 91 entries. What the extractor matches against and what
# ArticleTopic.normalized stores. Every leaf must reference a parent slug.
# labels carries Greek (el) only; German (de) deferred to Task 14b. Source: docs/superpowers/taxonomy-translations-draft.md
LEAVES = [
    # --- governance ---
    {'slug': 'accountability', 'label_en': 'Accountability', 'parent': 'governance', 'labels': {'el': 'Λογοδοσία'}},
    {'slug': 'anti_corruption', 'label_en': 'Anti-Corruption', 'parent': 'governance', 'labels': {'el': 'Καταπολέμηση της Διαφθοράς'}},
    {'slug': 'electoral_systems', 'label_en': 'Electoral Systems', 'parent': 'governance', 'labels': {'el': 'Εκλογικά Συστήματα'}},
    {'slug': 'government_transparency', 'label_en': 'Government Transparency', 'parent': 'governance', 'labels': {'el': 'Διαφάνεια στη Διακυβέρνηση'}},
    {'slug': 'institutional_trust', 'label_en': 'Institutional Trust', 'parent': 'governance', 'labels': {'el': 'Θεσμική Εμπιστοσύνη'}},
    {'slug': 'local_governance', 'label_en': 'Local Governance', 'parent': 'governance', 'labels': {'el': 'Τοπική Αυτοδιοίκηση'}},
    {'slug': 'public_procurement', 'label_en': 'Public Procurement', 'parent': 'governance', 'labels': {'el': 'Δημόσιες Συμβάσεις'}},
    {'slug': 'regional_policy', 'label_en': 'Regional & Territorial Policy', 'parent': 'governance', 'labels': {'el': 'Περιφερειακή & Χωροταξική Πολιτική'}},
    {'slug': 'rule_of_law', 'label_en': 'Rule of Law', 'parent': 'governance', 'labels': {'el': 'Κράτος Δικαίου'}},
    {'slug': 'voting_and_elections', 'label_en': 'Voting and Elections', 'parent': 'governance', 'labels': {'el': 'Ψηφοφορία & Εκλογές'}},
    # --- participation ---
    {'slug': 'citizen_assemblies', 'label_en': 'Citizen Assemblies', 'parent': 'participation', 'labels': {'el': 'Συνελεύσεις Πολιτών'}},
    {'slug': 'citizen_participation', 'label_en': 'Civic Participation', 'parent': 'participation', 'labels': {'el': 'Συμμετοχικότητα Πολιτών'}},
    {'slug': 'e_participation', 'label_en': 'E-Participation & Digital Engagement', 'parent': 'participation', 'labels': {'el': 'Ηλεκτρονική & Ψηφιακή Συμμετοχικότητα'}},
    {'slug': 'public_consultation', 'label_en': 'Public Consultation', 'parent': 'participation', 'labels': {'el': 'Δημόσια Διαβούλευση'}},
    # --- economic_fiscal ---
    {'slug': 'consumer_protection', 'label_en': 'Consumer Protection', 'parent': 'economic_fiscal', 'labels': {'el': 'Προστασία του Καταναλωτή'}},
    {'slug': 'economic_policy', 'label_en': 'Economic Policy', 'parent': 'economic_fiscal', 'labels': {'el': 'Οικονομική Πολιτική'}},
    {'slug': 'labour_and_employment', 'label_en': 'Labour and Employment', 'parent': 'economic_fiscal', 'labels': {'el': 'Εργασία & Απασχόληση'}},
    {'slug': 'labour_relations', 'label_en': 'Labour Relations & Trade Unions', 'parent': 'economic_fiscal', 'labels': {'el': 'Εργασιακές Σχέσεις & Συνδικαλισμός'}},
    {'slug': 'public_finance', 'label_en': 'Public Finance', 'parent': 'economic_fiscal', 'labels': {'el': 'Δημόσια Οικονομικά'}},
    {'slug': 'taxation', 'label_en': 'Taxation', 'parent': 'economic_fiscal', 'labels': {'el': 'Φορολογική Πολιτική'}},
    # --- social ---
    {'slug': 'companion_animals', 'label_en': 'Companion Animals', 'parent': 'social', 'labels': {'el': 'Ζώα Συντροφιάς'}},
    {'slug': 'inequality', 'label_en': 'Inequality', 'parent': 'social', 'labels': {'el': 'Ανισότητα'}},
    {'slug': 'intergenerational_justice', 'label_en': 'Intergenerational Justice', 'parent': 'social', 'labels': {'el': 'Διαγενεακή Δικαιοσύνη'}},
    {'slug': 'pensions', 'label_en': 'Pensions & Social Insurance', 'parent': 'social', 'labels': {'el': 'Συντάξεις & Κοινωνική Ασφάλιση'}},
    {'slug': 'social_cohesion', 'label_en': 'Social Cohesion', 'parent': 'social', 'labels': {'el': 'Κοινωνική Συνοχή'}},
    {'slug': 'social_justice', 'label_en': 'Social Justice', 'parent': 'social', 'labels': {'el': 'Κοινωνική Δικαιοσύνη'}},
    {'slug': 'social_welfare', 'label_en': 'Social Welfare & Benefits', 'parent': 'social', 'labels': {'el': 'Κοινωνική Πρόνοια & Παροχές'}},
    {'slug': 'youth_policy', 'label_en': 'Youth Policy', 'parent': 'social', 'labels': {'el': 'Πολιτική για τη Νεολαία'}},
    # --- health ---
    {'slug': 'healthcare_policy', 'label_en': 'Healthcare Policy', 'parent': 'health', 'labels': {'el': 'Υγειονομική Πολιτική'}},
    {'slug': 'long_term_care', 'label_en': 'Long-Term Care', 'parent': 'health', 'labels': {'el': 'Μακροχρόνια Φροντίδα'}},
    {'slug': 'mental_health', 'label_en': 'Mental Health', 'parent': 'health', 'labels': {'el': 'Ψυχική Υγεία'}},
    {'slug': 'public_health', 'label_en': 'Public Health', 'parent': 'health', 'labels': {'el': 'Δημόσια Υγεία'}},
    # --- education ---
    {'slug': 'early_childhood_education', 'label_en': 'Early Childhood Education', 'parent': 'education', 'labels': {'el': 'Προσχολική Εκπαίδευση & Φροντίδα'}},
    {'slug': 'education_funding', 'label_en': 'Education Funding', 'parent': 'education', 'labels': {'el': 'Χρηματοδότηση της Εκπαίδευσης'}},
    {'slug': 'education_policy', 'label_en': 'Education Policy', 'parent': 'education', 'labels': {'el': 'Εκπαιδευτική Πολιτική'}},
    {'slug': 'higher_education', 'label_en': 'Higher Education', 'parent': 'education', 'labels': {'el': 'Τριτοβάθμια Εκπαίδευση'}},
    {'slug': 'teacher_staffing', 'label_en': 'Teacher Staffing & Pay', 'parent': 'education', 'labels': {'el': 'Στελέχωση & Αμοιβές Εκπαιδευτικών'}},
    {'slug': 'vocational_education', 'label_en': 'Vocational Education & Training', 'parent': 'education', 'labels': {'el': 'Επαγγελματική Εκπαίδευση & Κατάρτιση'}},
    # --- justice_rights ---
    {'slug': 'accessibility', 'label_en': 'Accessibility', 'parent': 'justice_rights', 'labels': {'el': 'Προσβασιμότητα'}},
    {'slug': 'child_welfare', 'label_en': 'Child Welfare & Protection', 'parent': 'justice_rights', 'labels': {'el': 'Παιδική Μέριμνα & Προστασία'}},
    {'slug': 'civil_liberties', 'label_en': 'Civil Liberties', 'parent': 'justice_rights', 'labels': {'el': 'Ατομικές Ελευθερίες'}},
    {'slug': 'disability_rights', 'label_en': 'Disability Rights & Access', 'parent': 'justice_rights', 'labels': {'el': 'Δικαιώματα & Προσβασιμότητα Ατόμων με Αναπηρία (ΑμεΑ)'}},
    {'slug': 'freedom_of_expression', 'label_en': 'Freedom of Expression', 'parent': 'justice_rights', 'labels': {'el': 'Ελευθερία της Έκφρασης'}},
    {'slug': 'gender_equality', 'label_en': 'Gender Equality', 'parent': 'justice_rights', 'labels': {'el': 'Ισότητα των Φύλων'}},
    {'slug': 'human_rights', 'label_en': 'Human Rights', 'parent': 'justice_rights', 'labels': {'el': 'Ανθρώπινα Δικαιώματα'}},
    {'slug': 'judicial_reform', 'label_en': 'Judicial Reform', 'parent': 'justice_rights', 'labels': {'el': 'Δικαστική Μεταρρύθμιση'}},
    {'slug': 'minority_rights', 'label_en': 'Minority Rights', 'parent': 'justice_rights', 'labels': {'el': 'Δικαιώματα Μειονοτήτων'}},
    {'slug': 'police_reform', 'label_en': 'Police Reform & Accountability', 'parent': 'justice_rights', 'labels': {'el': 'Αστυνομική Μεταρρύθμιση & Λογοδοσία'}},
    # --- environment ---
    {'slug': 'biodiversity', 'label_en': 'Biodiversity & Nature Protection', 'parent': 'environment', 'labels': {'el': 'Βιοποικιλότητα & Προστασία της Φύσης'}},
    {'slug': 'climate_adaptation', 'label_en': 'Climate Adaptation', 'parent': 'environment', 'labels': {'el': 'Κλιματική Προσαρμογή'}},
    {'slug': 'climate_change', 'label_en': 'Climate Change', 'parent': 'environment', 'labels': {'el': 'Κλιματική Αλλαγή'}},
    {'slug': 'environmental_policy', 'label_en': 'Environmental Policy', 'parent': 'environment', 'labels': {'el': 'Περιβαλλοντική Πολιτική'}},
    {'slug': 'waste_management', 'label_en': 'Waste Management & Circular Economy', 'parent': 'environment', 'labels': {'el': 'Διαχείριση Αποβλήτων & Κυκλική Οικονομία'}},
    {'slug': 'water_management', 'label_en': 'Water Management', 'parent': 'environment', 'labels': {'el': 'Διαχείριση Υδάτων'}},
    {'slug': 'wildlife_protection', 'label_en': 'Wildlife Protection', 'parent': 'environment', 'labels': {'el': 'Προστασία Άγριας Ζωής'}},
    # --- energy ---
    {'slug': 'energy_poverty', 'label_en': 'Energy Poverty', 'parent': 'energy', 'labels': {'el': 'Ενεργειακή Πενία'}},
    {'slug': 'energy_transition', 'label_en': 'Energy Transition', 'parent': 'energy', 'labels': {'el': 'Ενεργειακή Μετάβαση'}},
    {'slug': 'renewable_energy', 'label_en': 'Renewable Energy', 'parent': 'energy', 'labels': {'el': 'Ανανεώσιμες Πηγές Ενέργειας (ΑΠΕ)'}},
    # --- transport ---
    {'slug': 'public_transport', 'label_en': 'Public Transport', 'parent': 'transport', 'labels': {'el': 'Δημόσιες Συγκοινωνίες'}},
    {'slug': 'road_infrastructure', 'label_en': 'Road Infrastructure', 'parent': 'transport', 'labels': {'el': 'Οδική Υποδομή'}},
    {'slug': 'transportation', 'label_en': 'Transportation', 'parent': 'transport', 'labels': {'el': 'Μεταφορές'}},
    # --- housing_urban ---
    {'slug': 'housing', 'label_en': 'Housing', 'parent': 'housing_urban', 'labels': {'el': 'Στέγαση'}},
    {'slug': 'housing_affordability', 'label_en': 'Housing Affordability', 'parent': 'housing_urban', 'labels': {'el': 'Ευχέρεια Στέγασης'}},
    {'slug': 'land_use', 'label_en': 'Land Use & Planning', 'parent': 'housing_urban', 'labels': {'el': 'Χρήσεις Γης & Χωροταξία'}},
    {'slug': 'urban_development', 'label_en': 'Urban Development', 'parent': 'housing_urban', 'labels': {'el': 'Αστική Ανάπτυξη'}},
    # --- agriculture_rural ---
    {'slug': 'agriculture', 'label_en': 'Agricultural Policy', 'parent': 'agriculture_rural', 'labels': {'el': 'Αγροτική Πολιτική'}},
    {'slug': 'food_safety', 'label_en': 'Food Safety', 'parent': 'agriculture_rural', 'labels': {'el': 'Ασφάλεια Τροφίμων'}},
    {'slug': 'livestock_welfare', 'label_en': 'Livestock Welfare', 'parent': 'agriculture_rural', 'labels': {'el': 'Ευημερία των Αγροτικών Ζώων'}},
    {'slug': 'rural_development', 'label_en': 'Rural Development', 'parent': 'agriculture_rural', 'labels': {'el': 'Αγροτική Ανάπτυξη'}},
    # --- technology ---
    {'slug': 'algorithmic_decision_making', 'label_en': 'Algorithmic Decision Making', 'parent': 'technology', 'labels': {'el': 'Αλγοριθμική Λήψη Αποφάσεων'}},
    {'slug': 'artificial_intelligence', 'label_en': 'Artificial Intelligence', 'parent': 'technology', 'labels': {'el': 'Τεχνητή Νοημοσύνη'}},
    {'slug': 'automation', 'label_en': 'Automation', 'parent': 'technology', 'labels': {'el': 'Αυτοματοποίηση'}},
    {'slug': 'bias_and_fairness', 'label_en': 'Bias and Fairness', 'parent': 'technology', 'labels': {'el': 'Προκατάληψη & Αμεροληψία'}},
    {'slug': 'cybersecurity', 'label_en': 'Cybersecurity', 'parent': 'technology', 'labels': {'el': 'Κυβερνοασφάλεια'}},
    {'slug': 'data_governance', 'label_en': 'Data Governance', 'parent': 'technology', 'labels': {'el': 'Διακυβέρνηση Δεδομένων'}},
    {'slug': 'digital_inclusion', 'label_en': 'Digital Inclusion', 'parent': 'technology', 'labels': {'el': 'Ψηφιακή Ένταξη'}},
    {'slug': 'digital_platforms', 'label_en': 'Digital Platforms', 'parent': 'technology', 'labels': {'el': 'Ψηφιακές Πλατφόρμες'}},
    {'slug': 'privacy_and_data_protection', 'label_en': 'Privacy and Data Protection', 'parent': 'technology', 'labels': {'el': 'Ιδιωτικότητα & Προστασία Δεδομένων'}},
    {'slug': 'surveillance_technologies', 'label_en': 'Surveillance Technologies', 'parent': 'technology', 'labels': {'el': 'Τεχνολογίες Παρακολούθησης'}},
    # --- media_information ---
    {'slug': 'media_education', 'label_en': 'Media & Digital Literacy', 'parent': 'media_information', 'labels': {'el': 'Μέσα Ενημέρωσης & Ψηφιακός Γραμματισμός'}},
    {'slug': 'media_regulation', 'label_en': 'Media Regulation', 'parent': 'media_information', 'labels': {'el': 'Έλεγχος Μέσων Ενημέρωσης'}},
    {'slug': 'misinformation', 'label_en': 'Misinformation', 'parent': 'media_information', 'labels': {'el': 'Παραπληροφόρηση'}},
    {'slug': 'platform_regulation', 'label_en': 'Platform & Online Services Regulation', 'parent': 'media_information', 'labels': {'el': 'Έλεγχος Πλατφορμών & Διαδικτυακών Υπηρεσιών'}},
    # --- culture_heritage ---
    {'slug': 'cultural_heritage', 'label_en': 'Cultural Heritage', 'parent': 'culture_heritage', 'labels': {'el': 'Πολιτιστική Κληρονομιά'}},
    {'slug': 'cultural_policy', 'label_en': 'Cultural Policy', 'parent': 'culture_heritage', 'labels': {'el': 'Πολιτιστική Πολιτική'}},
    {'slug': 'language_policy', 'label_en': 'Language & Minority Language Policy', 'parent': 'culture_heritage', 'labels': {'el': 'Γλωσσική Πολιτική & Πολιτική Μειονοτικών Γλωσσών'}},
    {'slug': 'sports_policy', 'label_en': 'Sports & Physical Activity Policy', 'parent': 'culture_heritage', 'labels': {'el': 'Αθλητική Πολιτική & Φυσική Αγωγή'}},
    # --- migration ---
    {'slug': 'migration_policy', 'label_en': 'Migration Policy', 'parent': 'migration', 'labels': {'el': 'Μεταναστευτική Πολιτική'}},
    {'slug': 'refugee_integration', 'label_en': 'Refugee & Asylum Policy', 'parent': 'migration', 'labels': {'el': 'Πολιτική Προσφύγων & Ασύλου'}},
    # --- public_safety (empty in this phase — no leaves) ---
    # --- foreign_affairs ---
    {'slug': 'defence', 'label_en': 'Defence & Security Policy', 'parent': 'foreign_affairs', 'labels': {'el': 'Άμυνα & Πολιτική Ασφάλειας'}},
    {'slug': 'eu_affairs', 'label_en': 'EU Affairs & European Integration', 'parent': 'foreign_affairs', 'labels': {'el': 'Ευρωπαϊκές Υποθέσεις & Ευρωπαϊκή Ολοκλήρωση'}},
]

# Backward-compat shim. Some legacy code paths and tests still import INITIAL_TOPICS.
# Compose it from LEAVES so nothing breaks until those call sites are migrated
# (seed_taxonomy refactor is Task 7).
INITIAL_TOPICS = [(leaf['slug'], leaf['label_en']) for leaf in LEAVES]
