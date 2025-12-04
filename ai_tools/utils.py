import numpy as np
from scipy.special import expit
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import CountVectorizer
from transformers import AutoTokenizer, AutoModelForSequenceClassification


def categorization(texts):
    # Source to be determined
    #texts = []
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
        return predictions


def categorization_cluster():
    # Load a multilingual embedding model:
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    texts = []

    # Generate embeddings:
    embeddings = model.encode(texts)
    # Define number of topics (clusters):
    num_topics = 3
    kmeans = KMeans(n_clusters=num_topics, random_state=10)
    # Fit and predict:
    clusters = kmeans.fit_predict(embeddings)

    # Print results
    #for i, text in enumerate(texts):
    #    print(f"Text: {text} -> Topic: {clusters[i]}")

    # Find top texts for each cluster
    for cluster_id in range(num_topics):
        cluster_texts = np.array(texts)[clusters == cluster_id]
        print(f"Cluster {cluster_id} Texts: {cluster_texts}")
        vectorizer = CountVectorizer(stop_words="english", token_pattern=r'(?u)\b\w\w\w+\b', analyzer='word')
        word_counts = vectorizer.fit_transform(cluster_texts)
        common_words = vectorizer.get_feature_names_out()
        print(f"Cluster {cluster_id} Key Words: {common_words[:10]}")
