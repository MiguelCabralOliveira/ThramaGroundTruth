import pinecone

# Connect to Pinecone
pc = pinecone.Pinecone(api_key="pcsk_3tehtu_BG3jLC57ZPwaFDd33K1AhAr8aVyrc3uv4w8pRLcwmvvqxeZ6WEnJvfsXjoQXy2")
index = pc.Index("tharma")

# Delete all vectors in a specific namespace
index.delete(delete_all=True, namespace="__default__")