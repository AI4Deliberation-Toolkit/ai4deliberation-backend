# Taxonomy version. Bump on every edit affecting slugs, labels, or parent assignments.
# Format: YYYY-MM-DD-N (N is the daily revision counter, starting at 1).
TAXONOMY_VERSION = '2026-05-21-1'

# Parent categories. 18 entries. Used only for aggregation (clustering rollups,
# dashboard summaries). The extractor never returns a parent slug as topic_id.
# labels carries Greek (el) and provisional German (de). German labels were Sonnet-drafted 2026-05-19 and applied 2026-05-21 to unblock the staging entrypoint validation; they have NOT been reviewed by a native German speaker yet. When a reviewer becomes available, they edit the draft file in place and a follow-up commit reapplies. Source: docs/superpowers/taxonomy-translations-draft.md
PARENTS = [
    {'slug': 'governance', 'label_en': 'Governance & Institutions', 'labels': {'el': 'Διακυβέρνηση & Θεσμοί', 'de': 'Regierungsführung & Institutionen'}},
    {'slug': 'participation', 'label_en': 'Participation & Deliberation', 'labels': {'el': 'Συμμετοχή & Διαβούλευση', 'de': 'Bürgerbeteiligung & Deliberation'}},
    {'slug': 'economic_fiscal', 'label_en': 'Economic & Fiscal Policy', 'labels': {'el': 'Οικονομική & Δημοσιονομική Πολιτική', 'de': 'Wirtschafts- und Finanzpolitik'}},
    {'slug': 'social', 'label_en': 'Social Policy & Welfare', 'labels': {'el': 'Κοινωνική Πολιτική & Πρόνοια', 'de': 'Sozialpolitik & Wohlfahrt'}},
    {'slug': 'health', 'label_en': 'Health & Welfare', 'labels': {'el': 'Υγεία & Υγειονομική Περίθαλψη', 'de': 'Gesundheit & Wohlfahrt'}},
    {'slug': 'education', 'label_en': 'Education', 'labels': {'el': 'Εκπαίδευση', 'de': 'Bildung'}},
    {'slug': 'justice_rights', 'label_en': 'Justice & Rights', 'labels': {'el': 'Δικαιοσύνη & Δικαιώματα', 'de': 'Justiz & Rechte'}},
    {'slug': 'environment', 'label_en': 'Environment & Climate', 'labels': {'el': 'Περιβάλλον & Κλίμα', 'de': 'Umwelt & Klima'}},
    {'slug': 'energy', 'label_en': 'Energy & Resources', 'labels': {'el': 'Ενέργεια & Πόροι', 'de': 'Energie & Ressourcen'}},
    {'slug': 'transport', 'label_en': 'Transportation & Mobility', 'labels': {'el': 'Μεταφορές & Κινητικότητα', 'de': 'Verkehr & Mobilität'}},
    {'slug': 'housing_urban', 'label_en': 'Housing & Urban Development', 'labels': {'el': 'Στέγαση & Αστική Ανάπτυξη', 'de': 'Wohnen & Stadtentwicklung'}},
    {'slug': 'agriculture_rural', 'label_en': 'Agriculture & Rural Development', 'labels': {'el': 'Γεωργία & Αγροτική Ανάπτυξη', 'de': 'Landwirtschaft & Ländliche Entwicklung'}},
    {'slug': 'technology', 'label_en': 'Technology & Digital', 'labels': {'el': 'Τεχνολογία & Ψηφιακή Πολιτική', 'de': 'Technologie & Digitales'}},
    {'slug': 'media_information', 'label_en': 'Media & Information', 'labels': {'el': 'Μέσα Ενημέρωσης & Πληροφορία', 'de': 'Medien & Information'}},
    {'slug': 'culture_heritage', 'label_en': 'Culture & Heritage', 'labels': {'el': 'Πολιτισμός & Πολιτιστική Κληρονομιά', 'de': 'Kultur & kulturelles Erbe'}},
    {'slug': 'migration', 'label_en': 'Migration & Integration', 'labels': {'el': 'Μετανάστευση & Ένταξη', 'de': 'Migration & Integration'}},
    {'slug': 'public_safety', 'label_en': 'Public Safety & Security', 'labels': {'el': 'Δημόσια Ασφάλεια & Τάξη', 'de': 'Öffentliche Sicherheit & Ordnung'}},
    {'slug': 'foreign_affairs', 'label_en': 'Foreign Affairs & International', 'labels': {'el': 'Εξωτερικές Υποθέσεις & Διεθνείς Σχέσεις', 'de': 'Auswärtige Angelegenheiten & Internationales'}},
]

# Leaf topics. 91 entries. What the extractor matches against and what
# ArticleTopic.normalized stores. Every leaf must reference a parent slug.
# labels carries Greek (el) and provisional German (de). German labels were Sonnet-drafted 2026-05-19 and applied 2026-05-21 to unblock the staging entrypoint validation; they have NOT been reviewed by a native German speaker yet. When a reviewer becomes available, they edit the draft file in place and a follow-up commit reapplies. Source: docs/superpowers/taxonomy-translations-draft.md
LEAVES = [
    # --- governance ---
    {'slug': 'accountability', 'label_en': 'Accountability', 'parent': 'governance', 'labels': {'el': 'Λογοδοσία', 'de': 'Rechenschaftspflicht'}},
    {'slug': 'anti_corruption', 'label_en': 'Anti-Corruption', 'parent': 'governance', 'labels': {'el': 'Καταπολέμηση της Διαφθοράς', 'de': 'Korruptionsbekämpfung'}},
    {'slug': 'electoral_systems', 'label_en': 'Electoral Systems', 'parent': 'governance', 'labels': {'el': 'Εκλογικά Συστήματα', 'de': 'Wahlsysteme'}},
    {'slug': 'government_transparency', 'label_en': 'Government Transparency', 'parent': 'governance', 'labels': {'el': 'Διαφάνεια στη Διακυβέρνηση', 'de': 'Regierungstransparenz'}},
    {'slug': 'institutional_trust', 'label_en': 'Institutional Trust', 'parent': 'governance', 'labels': {'el': 'Θεσμική Εμπιστοσύνη', 'de': 'Institutionenvertrauen'}},
    {'slug': 'local_governance', 'label_en': 'Local Governance', 'parent': 'governance', 'labels': {'el': 'Τοπική Αυτοδιοίκηση', 'de': 'Kommunale Selbstverwaltung'}},
    {'slug': 'public_procurement', 'label_en': 'Public Procurement', 'parent': 'governance', 'labels': {'el': 'Δημόσιες Συμβάσεις', 'de': 'Öffentliche Auftragsvergabe'}},
    {'slug': 'regional_policy', 'label_en': 'Regional & Territorial Policy', 'parent': 'governance', 'labels': {'el': 'Περιφερειακή & Χωροταξική Πολιτική', 'de': 'Regional- und Raumordnungspolitik'}},
    {'slug': 'rule_of_law', 'label_en': 'Rule of Law', 'parent': 'governance', 'labels': {'el': 'Κράτος Δικαίου', 'de': 'Rechtsstaatlichkeit'}},
    {'slug': 'voting_and_elections', 'label_en': 'Voting and Elections', 'parent': 'governance', 'labels': {'el': 'Ψηφοφορία & Εκλογές', 'de': 'Abstimmung und Wahlen'}},
    # --- participation ---
    {'slug': 'citizen_assemblies', 'label_en': 'Citizen Assemblies', 'parent': 'participation', 'labels': {'el': 'Συνελεύσεις Πολιτών', 'de': 'Bürgerräte'}},
    {'slug': 'citizen_participation', 'label_en': 'Civic Participation', 'parent': 'participation', 'labels': {'el': 'Συμμετοχικότητα Πολιτών', 'de': 'Zivilgesellschaftliche Beteiligung'}},
    {'slug': 'e_participation', 'label_en': 'E-Participation & Digital Engagement', 'parent': 'participation', 'labels': {'el': 'Ηλεκτρονική & Ψηφιακή Συμμετοχικότητα', 'de': 'E-Partizipation & Digitales Engagement'}},
    {'slug': 'public_consultation', 'label_en': 'Public Consultation', 'parent': 'participation', 'labels': {'el': 'Δημόσια Διαβούλευση', 'de': 'Öffentliche Konsultation'}},
    # --- economic_fiscal ---
    {'slug': 'consumer_protection', 'label_en': 'Consumer Protection', 'parent': 'economic_fiscal', 'labels': {'el': 'Προστασία του Καταναλωτή', 'de': 'Verbraucherschutz'}},
    {'slug': 'economic_policy', 'label_en': 'Economic Policy', 'parent': 'economic_fiscal', 'labels': {'el': 'Οικονομική Πολιτική', 'de': 'Wirtschaftspolitik'}},
    {'slug': 'labour_and_employment', 'label_en': 'Labour and Employment', 'parent': 'economic_fiscal', 'labels': {'el': 'Εργασία & Απασχόληση', 'de': 'Arbeit und Beschäftigung'}},
    {'slug': 'labour_relations', 'label_en': 'Labour Relations & Trade Unions', 'parent': 'economic_fiscal', 'labels': {'el': 'Εργασιακές Σχέσεις & Συνδικαλισμός', 'de': 'Arbeitsbeziehungen & Gewerkschaften'}},
    {'slug': 'public_finance', 'label_en': 'Public Finance', 'parent': 'economic_fiscal', 'labels': {'el': 'Δημόσια Οικονομικά', 'de': 'Öffentliche Finanzen'}},
    {'slug': 'taxation', 'label_en': 'Taxation', 'parent': 'economic_fiscal', 'labels': {'el': 'Φορολογική Πολιτική', 'de': 'Besteuerung'}},
    # --- social ---
    {'slug': 'companion_animals', 'label_en': 'Companion Animals', 'parent': 'social', 'labels': {'el': 'Ζώα Συντροφιάς', 'de': 'Heimtiere'}},
    {'slug': 'inequality', 'label_en': 'Inequality', 'parent': 'social', 'labels': {'el': 'Ανισότητα', 'de': 'Ungleichheit'}},
    {'slug': 'intergenerational_justice', 'label_en': 'Intergenerational Justice', 'parent': 'social', 'labels': {'el': 'Διαγενεακή Δικαιοσύνη', 'de': 'Generationengerechtigkeit'}},
    {'slug': 'pensions', 'label_en': 'Pensions & Social Insurance', 'parent': 'social', 'labels': {'el': 'Συντάξεις & Κοινωνική Ασφάλιση', 'de': 'Renten & Sozialversicherung'}},
    {'slug': 'social_cohesion', 'label_en': 'Social Cohesion', 'parent': 'social', 'labels': {'el': 'Κοινωνική Συνοχή', 'de': 'Sozialer Zusammenhalt'}},
    {'slug': 'social_justice', 'label_en': 'Social Justice', 'parent': 'social', 'labels': {'el': 'Κοινωνική Δικαιοσύνη', 'de': 'Soziale Gerechtigkeit'}},
    {'slug': 'social_welfare', 'label_en': 'Social Welfare & Benefits', 'parent': 'social', 'labels': {'el': 'Κοινωνική Πρόνοια & Παροχές', 'de': 'Soziale Wohlfahrt & Sozialleistungen'}},
    {'slug': 'youth_policy', 'label_en': 'Youth Policy', 'parent': 'social', 'labels': {'el': 'Πολιτική για τη Νεολαία', 'de': 'Jugendpolitik'}},
    # --- health ---
    {'slug': 'healthcare_policy', 'label_en': 'Healthcare Policy', 'parent': 'health', 'labels': {'el': 'Υγειονομική Πολιτική', 'de': 'Gesundheitspolitik'}},
    {'slug': 'long_term_care', 'label_en': 'Long-Term Care', 'parent': 'health', 'labels': {'el': 'Μακροχρόνια Φροντίδα', 'de': 'Langzeitpflege'}},
    {'slug': 'mental_health', 'label_en': 'Mental Health', 'parent': 'health', 'labels': {'el': 'Ψυχική Υγεία', 'de': 'Psychische Gesundheit'}},
    {'slug': 'public_health', 'label_en': 'Public Health', 'parent': 'health', 'labels': {'el': 'Δημόσια Υγεία', 'de': 'Öffentliche Gesundheit'}},
    # --- education ---
    {'slug': 'early_childhood_education', 'label_en': 'Early Childhood Education', 'parent': 'education', 'labels': {'el': 'Προσχολική Εκπαίδευση & Φροντίδα', 'de': 'Frühkindliche Bildung und Betreuung'}},
    {'slug': 'education_funding', 'label_en': 'Education Funding', 'parent': 'education', 'labels': {'el': 'Χρηματοδότηση της Εκπαίδευσης', 'de': 'Bildungsfinanzierung'}},
    {'slug': 'education_policy', 'label_en': 'Education Policy', 'parent': 'education', 'labels': {'el': 'Εκπαιδευτική Πολιτική', 'de': 'Bildungspolitik'}},
    {'slug': 'higher_education', 'label_en': 'Higher Education', 'parent': 'education', 'labels': {'el': 'Τριτοβάθμια Εκπαίδευση', 'de': 'Hochschulbildung'}},
    {'slug': 'teacher_staffing', 'label_en': 'Teacher Staffing & Pay', 'parent': 'education', 'labels': {'el': 'Στελέχωση & Αμοιβές Εκπαιδευτικών', 'de': 'Lehrerstellen & Lehrergehälter'}},
    {'slug': 'vocational_education', 'label_en': 'Vocational Education & Training', 'parent': 'education', 'labels': {'el': 'Επαγγελματική Εκπαίδευση & Κατάρτιση', 'de': 'Berufliche Bildung und Ausbildung'}},
    # --- justice_rights ---
    {'slug': 'accessibility', 'label_en': 'Accessibility', 'parent': 'justice_rights', 'labels': {'el': 'Προσβασιμότητα', 'de': 'Barrierefreiheit'}},
    {'slug': 'child_welfare', 'label_en': 'Child Welfare & Protection', 'parent': 'justice_rights', 'labels': {'el': 'Παιδική Μέριμνα & Προστασία', 'de': 'Kinderschutz & Kindeswohl'}},
    {'slug': 'civil_liberties', 'label_en': 'Civil Liberties', 'parent': 'justice_rights', 'labels': {'el': 'Ατομικές Ελευθερίες', 'de': 'Bürgerliche Freiheiten'}},
    {'slug': 'disability_rights', 'label_en': 'Disability Rights & Access', 'parent': 'justice_rights', 'labels': {'el': 'Δικαιώματα & Προσβασιμότητα Ατόμων με Αναπηρία (ΑμεΑ)', 'de': 'Rechte von Menschen mit Behinderung & Zugang'}},
    {'slug': 'freedom_of_expression', 'label_en': 'Freedom of Expression', 'parent': 'justice_rights', 'labels': {'el': 'Ελευθερία της Έκφρασης', 'de': 'Meinungsfreiheit'}},
    {'slug': 'gender_equality', 'label_en': 'Gender Equality', 'parent': 'justice_rights', 'labels': {'el': 'Ισότητα των Φύλων', 'de': 'Geschlechtergleichstellung'}},
    {'slug': 'human_rights', 'label_en': 'Human Rights', 'parent': 'justice_rights', 'labels': {'el': 'Ανθρώπινα Δικαιώματα', 'de': 'Menschenrechte'}},
    {'slug': 'judicial_reform', 'label_en': 'Judicial Reform', 'parent': 'justice_rights', 'labels': {'el': 'Δικαστική Μεταρρύθμιση', 'de': 'Justizreform'}},
    {'slug': 'minority_rights', 'label_en': 'Minority Rights', 'parent': 'justice_rights', 'labels': {'el': 'Δικαιώματα Μειονοτήτων', 'de': 'Minderheitenrechte'}},
    {'slug': 'police_reform', 'label_en': 'Police Reform & Accountability', 'parent': 'justice_rights', 'labels': {'el': 'Αστυνομική Μεταρρύθμιση & Λογοδοσία', 'de': 'Polizeireform & Rechenschaftspflicht'}},
    # --- environment ---
    {'slug': 'biodiversity', 'label_en': 'Biodiversity & Nature Protection', 'parent': 'environment', 'labels': {'el': 'Βιοποικιλότητα & Προστασία της Φύσης', 'de': 'Biodiversität & Naturschutz'}},
    {'slug': 'climate_adaptation', 'label_en': 'Climate Adaptation', 'parent': 'environment', 'labels': {'el': 'Κλιματική Προσαρμογή', 'de': 'Klimaanpassung'}},
    {'slug': 'climate_change', 'label_en': 'Climate Change', 'parent': 'environment', 'labels': {'el': 'Κλιματική Αλλαγή', 'de': 'Klimawandel'}},
    {'slug': 'environmental_policy', 'label_en': 'Environmental Policy', 'parent': 'environment', 'labels': {'el': 'Περιβαλλοντική Πολιτική', 'de': 'Umweltpolitik'}},
    {'slug': 'waste_management', 'label_en': 'Waste Management & Circular Economy', 'parent': 'environment', 'labels': {'el': 'Διαχείριση Αποβλήτων & Κυκλική Οικονομία', 'de': 'Abfallwirtschaft & Kreislaufwirtschaft'}},
    {'slug': 'water_management', 'label_en': 'Water Management', 'parent': 'environment', 'labels': {'el': 'Διαχείριση Υδάτων', 'de': 'Wasserwirtschaft'}},
    {'slug': 'wildlife_protection', 'label_en': 'Wildlife Protection', 'parent': 'environment', 'labels': {'el': 'Προστασία Άγριας Ζωής', 'de': 'Wildtierschutz'}},
    # --- energy ---
    {'slug': 'energy_poverty', 'label_en': 'Energy Poverty', 'parent': 'energy', 'labels': {'el': 'Ενεργειακή Πενία', 'de': 'Energiearmut'}},
    {'slug': 'energy_transition', 'label_en': 'Energy Transition', 'parent': 'energy', 'labels': {'el': 'Ενεργειακή Μετάβαση', 'de': 'Energiewende'}},
    {'slug': 'renewable_energy', 'label_en': 'Renewable Energy', 'parent': 'energy', 'labels': {'el': 'Ανανεώσιμες Πηγές Ενέργειας (ΑΠΕ)', 'de': 'Erneuerbare Energien'}},
    # --- transport ---
    {'slug': 'public_transport', 'label_en': 'Public Transport', 'parent': 'transport', 'labels': {'el': 'Δημόσιες Συγκοινωνίες', 'de': 'Öffentlicher Nahverkehr'}},
    {'slug': 'road_infrastructure', 'label_en': 'Road Infrastructure', 'parent': 'transport', 'labels': {'el': 'Οδική Υποδομή', 'de': 'Straßeninfrastruktur'}},
    {'slug': 'transportation', 'label_en': 'Transportation', 'parent': 'transport', 'labels': {'el': 'Μεταφορές', 'de': 'Verkehr'}},
    # --- housing_urban ---
    {'slug': 'housing', 'label_en': 'Housing', 'parent': 'housing_urban', 'labels': {'el': 'Στέγαση', 'de': 'Wohnungsbau'}},
    {'slug': 'housing_affordability', 'label_en': 'Housing Affordability', 'parent': 'housing_urban', 'labels': {'el': 'Ευχέρεια Στέγασης', 'de': 'Wohnkostenbelastung'}},
    {'slug': 'land_use', 'label_en': 'Land Use & Planning', 'parent': 'housing_urban', 'labels': {'el': 'Χρήσεις Γης & Χωροταξία', 'de': 'Bodennutzung & Raumplanung'}},
    {'slug': 'urban_development', 'label_en': 'Urban Development', 'parent': 'housing_urban', 'labels': {'el': 'Αστική Ανάπτυξη', 'de': 'Stadtentwicklung'}},
    # --- agriculture_rural ---
    {'slug': 'agriculture', 'label_en': 'Agricultural Policy', 'parent': 'agriculture_rural', 'labels': {'el': 'Αγροτική Πολιτική', 'de': 'Agrarpolitik'}},
    {'slug': 'food_safety', 'label_en': 'Food Safety', 'parent': 'agriculture_rural', 'labels': {'el': 'Ασφάλεια Τροφίμων', 'de': 'Lebensmittelsicherheit'}},
    {'slug': 'livestock_welfare', 'label_en': 'Livestock Welfare', 'parent': 'agriculture_rural', 'labels': {'el': 'Ευημερία των Αγροτικών Ζώων', 'de': 'Tierschutz in der Landwirtschaft'}},
    {'slug': 'rural_development', 'label_en': 'Rural Development', 'parent': 'agriculture_rural', 'labels': {'el': 'Αγροτική Ανάπτυξη', 'de': 'Ländliche Entwicklung'}},
    # --- technology ---
    {'slug': 'algorithmic_decision_making', 'label_en': 'Algorithmic Decision Making', 'parent': 'technology', 'labels': {'el': 'Αλγοριθμική Λήψη Αποφάσεων', 'de': 'Algorithmische Entscheidungsfindung'}},
    {'slug': 'artificial_intelligence', 'label_en': 'Artificial Intelligence', 'parent': 'technology', 'labels': {'el': 'Τεχνητή Νοημοσύνη', 'de': 'Künstliche Intelligenz'}},
    {'slug': 'automation', 'label_en': 'Automation', 'parent': 'technology', 'labels': {'el': 'Αυτοματοποίηση', 'de': 'Automatisierung'}},
    {'slug': 'bias_and_fairness', 'label_en': 'Bias and Fairness', 'parent': 'technology', 'labels': {'el': 'Προκατάληψη & Αμεροληψία', 'de': 'Voreingenommenheit und Fairness'}},
    {'slug': 'cybersecurity', 'label_en': 'Cybersecurity', 'parent': 'technology', 'labels': {'el': 'Κυβερνοασφάλεια', 'de': 'Cybersicherheit'}},
    {'slug': 'data_governance', 'label_en': 'Data Governance', 'parent': 'technology', 'labels': {'el': 'Διακυβέρνηση Δεδομένων', 'de': 'Datenverwaltung'}},
    {'slug': 'digital_inclusion', 'label_en': 'Digital Inclusion', 'parent': 'technology', 'labels': {'el': 'Ψηφιακή Ένταξη', 'de': 'Digitale Inklusion'}},
    {'slug': 'digital_platforms', 'label_en': 'Digital Platforms', 'parent': 'technology', 'labels': {'el': 'Ψηφιακές Πλατφόρμες', 'de': 'Digitale Plattformen'}},
    {'slug': 'privacy_and_data_protection', 'label_en': 'Privacy and Data Protection', 'parent': 'technology', 'labels': {'el': 'Ιδιωτικότητα & Προστασία Δεδομένων', 'de': 'Datenschutz und Privatsphäre'}},
    {'slug': 'surveillance_technologies', 'label_en': 'Surveillance Technologies', 'parent': 'technology', 'labels': {'el': 'Τεχνολογίες Παρακολούθησης', 'de': 'Überwachungstechnologien'}},
    # --- media_information ---
    {'slug': 'media_education', 'label_en': 'Media & Digital Literacy', 'parent': 'media_information', 'labels': {'el': 'Μέσα Ενημέρωσης & Ψηφιακός Γραμματισμός', 'de': 'Medienbildung & digitale Kompetenz'}},
    {'slug': 'media_regulation', 'label_en': 'Media Regulation', 'parent': 'media_information', 'labels': {'el': 'Έλεγχος Μέσων Ενημέρωσης', 'de': 'Medienregulierung'}},
    {'slug': 'misinformation', 'label_en': 'Misinformation', 'parent': 'media_information', 'labels': {'el': 'Παραπληροφόρηση', 'de': 'Fehlinformation'}},
    {'slug': 'platform_regulation', 'label_en': 'Platform & Online Services Regulation', 'parent': 'media_information', 'labels': {'el': 'Έλεγχος Πλατφορμών & Διαδικτυακών Υπηρεσιών', 'de': 'Plattformregulierung & Regulierung Online-Dienste'}},
    # --- culture_heritage ---
    {'slug': 'cultural_heritage', 'label_en': 'Cultural Heritage', 'parent': 'culture_heritage', 'labels': {'el': 'Πολιτιστική Κληρονομιά', 'de': 'Kulturelles Erbe'}},
    {'slug': 'cultural_policy', 'label_en': 'Cultural Policy', 'parent': 'culture_heritage', 'labels': {'el': 'Πολιτιστική Πολιτική', 'de': 'Kulturpolitik'}},
    {'slug': 'language_policy', 'label_en': 'Language & Minority Language Policy', 'parent': 'culture_heritage', 'labels': {'el': 'Γλωσσική Πολιτική & Πολιτική Μειονοτικών Γλωσσών', 'de': 'Sprach- und Minderheitensprachpolitik'}},
    {'slug': 'sports_policy', 'label_en': 'Sports & Physical Activity Policy', 'parent': 'culture_heritage', 'labels': {'el': 'Αθλητική Πολιτική & Φυσική Αγωγή', 'de': 'Sportpolitik & Bewegungsförderung'}},
    # --- migration ---
    {'slug': 'migration_policy', 'label_en': 'Migration Policy', 'parent': 'migration', 'labels': {'el': 'Μεταναστευτική Πολιτική', 'de': 'Migrationspolitik'}},
    {'slug': 'refugee_integration', 'label_en': 'Refugee & Asylum Policy', 'parent': 'migration', 'labels': {'el': 'Πολιτική Προσφύγων & Ασύλου', 'de': 'Flüchtlings- und Asylpolitik'}},
    # --- public_safety (empty in this phase — no leaves) ---
    # --- foreign_affairs ---
    {'slug': 'defence', 'label_en': 'Defence & Security Policy', 'parent': 'foreign_affairs', 'labels': {'el': 'Άμυνα & Πολιτική Ασφάλειας', 'de': 'Verteidigungs- und Sicherheitspolitik'}},
    {'slug': 'eu_affairs', 'label_en': 'EU Affairs & European Integration', 'parent': 'foreign_affairs', 'labels': {'el': 'Ευρωπαϊκές Υποθέσεις & Ευρωπαϊκή Ολοκλήρωση', 'de': 'EU-Angelegenheiten & Europäische Integration'}},
]

# Backward-compat shim. Some legacy code paths and tests still import INITIAL_TOPICS.
# Compose it from LEAVES so nothing breaks until those call sites are migrated
# (seed_taxonomy refactor is Task 7).
INITIAL_TOPICS = [(leaf['slug'], leaf['label_en']) for leaf in LEAVES]
