from scipy.special import expit
from transformers import AutoTokenizer, AutoModelForSequenceClassification


def categorization():
    # Source to be determined
    texts = []
    model_name = "cardiffnlp/tweet-topic-large-multilingual"
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    for text in texts:
        tokens = tokenizer(text, return_tensors='pt')
        output = model(**tokens)

        # Apply sigmoid to handle multi-label classification
        scores = expit(output.logits.detach().numpy()[0])

        # Threshold predictions
        threshold = 0.5
        predictions = (scores >= threshold).astype(int)

        # Map to topics
        topic_labels = model.config.id2label
        for idx, pred in enumerate(predictions):
            if pred:
                print(f"Predicted topic: {topic_labels[idx]}")
