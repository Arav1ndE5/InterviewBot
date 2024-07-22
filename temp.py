from pdf2jpg import pdf2jpg
import os
import cv2

resume_path = r"C:\Users\Aravind\Downloads\test ui.pdf"
output_path = r'D:\Projects--\InterviewBot\output'  # Use an absolute path for the output directory

# Ensure the output directory exists
if not os.path.exists(output_path):
    os.makedirs(output_path)

# Convert PDF to images using pdf2jpg
result = pdf2jpg.convert_pdf2jpg(resume_path, output_path, pages="ALL", dpi=200)

print(result)
print(output_path)

# Check if the result is as expected
if not isinstance(result, list) or not result:
    print("Conversion failed or no output generated.")
else:
    # Extract the list of generated image files
    images = []
    for img in result[0]['output_jpgfiles']:
        images.append(cv2.imread(img))

    print(images)

    # # Read and collect images
    # collection = []
    # for image_path in images:
    #     img = cv2.imread(image_path)
    #     if img is not None:
    #         collection.append(img)
    #     else:
    #         print(f"Failed to read image: {image_path}")

    # Concatenate images horizontally if there are images to concatenate
    if images:
        resume_image = cv2.hconcat(images)
        concatenated_image_path = os.path.join(output_path, "concatenated_resume.jpg")
        cv2.imwrite(concatenated_image_path, resume_image)
        print(f"Concatenated image saved at: {concatenated_image_path}")
    else:
        print("No images to concatenate.")
