from transformers import AutoTokenizer, AutoModelForSequenceClassification

# BioBERT (general biomedical text model)
biobert_name = "dmis-lab/biobert-base-cased-v1.1"
biobert_tokenizer = AutoTokenizer.from_pretrained(biobert_name)
biobert_model = AutoModelForSequenceClassification.from_pretrained(biobert_name)

# ClinicalBERT (trained on clinical notes like MIMIC-III)
clinibert_name = "emilyalsentzer/Bio_ClinicalBERT"
clinibert_tokenizer = AutoTokenizer.from_pretrained(clinibert_name)
clinibert_model = AutoModelForSequenceClassification.from_pretrained(clinibert_name)
