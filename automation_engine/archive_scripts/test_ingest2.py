from automation_engine.core.ingestion import DocumentIngestion
engine = DocumentIngestion("/Users/apple/Desktop/FLA/data/karomi")
docs = engine.find_documents()
print("Extracted docs:", docs)
