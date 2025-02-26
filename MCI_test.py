import MattyInvertor
import webbrowser

concept = "dada"
selected_axes = ["semantic", "causal", "emotional", "functional", "conceptual_abstract"]

# For MCI_v3
result = MattyInvertor.mci_v1(concept, selected_axes=selected_axes)
print(f"Orthogonal concept to {concept}:", result)

# Generate contrast image and open in browser
# Set is_mci_v3=True for MCI_v3 output
image_url = MattyInvertor.generate_contrast_image(concept, result, is_mci_v3=True)
print("Contrast Image URL:", image_url)
webbrowser.open(image_url)

# For MCI_v2, you would use:
# result = MattyInvertor.mci_v2(concept, depth=5, selected_axes=selected_axes)
# image_url = MattyInvertor.generate_contrast_image(concept, result, is_mci_v3=False)