from backend.services.ai_detect_service import detector_pipeline, _get_label

print(f"Model loaded: {detector_pipeline.model.name_or_path}")
text_sample = "The quick brown fox jumps over the lazy dog. This is just a sample for testing."
res = detector_pipeline(text_sample)[0]
print("Result for human text:", res)

ai_text = "As an AI language model, I can understand patterns."
res_ai = detector_pipeline(ai_text)[0]
print("Result for AI sounding text:", res_ai)
