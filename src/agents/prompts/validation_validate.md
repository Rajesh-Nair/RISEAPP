Validate the following classification result:

Original Transaction Text: "{original_text}"

Classification Result:
- Brand Name: {brand_name}
- Nature of Business: {nature_of_business}
- Category: {category_description}

Please validate:
1. Does the nature of business align with the category?
2. Is the brand name reasonable for the given transaction text?
3. Are there any logical inconsistencies?
4. Is this classification accurate and not hallucinated?

Return your response as a JSON object with:
- is_valid: true if classification is valid, false otherwise
- confidence: Your confidence in the validation (0.0 to 1.0)
- validation_notes: Brief explanation of your validation decision
