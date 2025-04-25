from langchain.agents import tool
import boto3
import os
import uuid
import vertexai
from vertexai.vision_models import ImageGenerationModel, Image
from PIL import Image as PILImage
from langchain.prompts import PromptTemplate
import io

s3_client = boto3.client("s3")


@tool
def gen_images(
    prompt: str,
    negative_prompt: str,
    add_watermark: bool = False,
    aspect_ratio: str = "1:1",
    guidance_scale: float = None,
):
    """Generate images.

    Args:
        prompt (str): The prompt text to generate image.
        negative_prompt (str): A description of what you want to omit in the generated images.
        add_watermark (bool): Add a watermark to the generated image
        aspect_ratio (str): Changes the aspect ratio of the generated image Supported
            values are:
            * "1:1" : 1:1 aspect ratio
            * "9:16" : 9:16 aspect ratio
            * "16:9" : 16:9 aspect ratio
            * "4:3" : 4:3 aspect ratio
            * "3:4" : 3:4 aspect_ratio
        guidance_scale (float): Controls the strength of the prompt. Suggested values are:
            * 0-9 (low strength)
            * 10-20 (medium strength)
            * 21+ (high strength)

    Returns:
       list[str]: Urls of image 
    """
    if prompt is None or prompt == "":
        return "Error:prompt is required."
    if aspect_ratio not in ["1:1", "9:16", "16:9", "3:4", "4:3"]:
        return """Error: aspect_ratio: Changes the aspect ratio of the generated image Supported
            values are:
            * "1:1" : 1:1 aspect ratio
            * "9:16" : 9:16 aspect ratio
            * "16:9" : 16:9 aspect ratio
            * "4:3" : 4:3 aspect ratio
            * "3:4" : 3:4 aspect_ratio"""
    vertexai.init(project="shining-expanse-398306", location="us-central1")
    model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
    resp = model.generate_images(
        prompt=prompt,
        guidance_scale=guidance_scale,
        negative_prompt=negative_prompt,
        aspect_ratio=aspect_ratio,
        add_watermark=add_watermark,
    )
    result_urls = []

    for i, img in enumerate(resp.images):
        temp_filename = f"generated_image_{uuid.uuid4()}.png"
        img.save(temp_filename)

        s3_key = f"images/{temp_filename}"
        s3_client.upload_file(
            temp_filename, "musse.ai", s3_key, ExtraArgs={"ContentType": "image/png"}
        )

        os.remove(temp_filename)

        # s3_url = f"![Generated Image {i+1}](https://musse.ai/{s3_key})"
        # s3_url = f"\n<img src='https://musse.ai/{s3_key}'>"
        s3_url = f"https://musse.ai/{s3_key}"
        result_urls.append(s3_url)

    return result_urls


@tool
def gen_images_2(prompt: str) -> str:
    """Generate images and return markdown format image links of generated images, saved in temp/images directory.
    Args:
        prompt (str): The prompt text to generate image.
    Returns:
        str: Markdown format image links of generated images, separated by newlines
    """
    vertexai.init(project="shining-expanse-398306", location="us-central1")
    model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")
    resp = model.generate_images(prompt=prompt)
    result_urls = []
    # Ensure temp/images directory exists
    os.makedirs("temp/images", exist_ok=True)
    for i, img in enumerate(resp.images):
        temp_filename = f"generated_image_{uuid.uuid4()}.png"
        save_path = os.path.join("temp/images", temp_filename)
        img.save(save_path)
        # Generate local URL path
        url = f"![Generated Image {i+1}](temp/images/{temp_filename})"
        result_urls.append(url)
    return "I have generated images for you. Here are the image paths:\n" + "\n".join(
        result_urls
    )


@tool
def generate_social_media_image(text: str):
    """
    Generate social media images using Imagen. This function combines given text and logo into a social media image.

    Args:
        text (str): Text content to be added
    Returns:
        list: List of generated image URLs
    """
    # Parameter validation
    if not isinstance(text, str) or not text.strip():
        return "Error: Text content cannot be empty"

    # Initialize Vertex AI
    vertexai.init(project="shining-expanse-398306", location="us-central1")

    # Load logo image
    # with PILImage.open("mlion_logo.png") as img:
    #     # Ensure image meets requirements (e.g., resize)
    #     # if img.mode != "RGB":
    #     #     img = img.convert("RGB")
    #     # Resize image to appropriate dimensions (e.g., 1024x1024)
    #     # img = img.resize((width, height))

    #     # Convert to bytes
    #     img_byte_arr = io.BytesIO()
    #     img.save(img_byte_arr, format="PNG")
    #     img_byte_arr = img_byte_arr.getvalue()

    # Create Image object
    input_image = Image.load_from_file("mlion_logo.png")

    # If no prompt template provided, use default template
    prompt_template = """
    Create a social media post image with the following elements:
    1. Use the provided logo as the main visual element
    2. Add the following text: "{text}"
    3. Style: Modern, clean, and professional
    4. Layout: Center-aligned, with appropriate spacing
    5. Background: Simple and complementary to the logo
    6. Text should be clearly readable
    """

    # Format prompt
    prompt = PromptTemplate.from_template(prompt_template)

    # Initialize Imagen model
    model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")

    # Generate image
    response = model.generate_images(
        prompt=prompt.format(text=text),
        aspect_ratio="9:16",
        # width=256,
        number_of_images=1,
        # base_image=input_image,
        # size=f"{width}x{height}",  # 或其他支持的尺寸
    )

    result_urls = []

    for i, img in enumerate(response.images):
        temp_filename = f"generated_image_{uuid.uuid4()}.png"
        img.save(temp_filename)

        s3_key = f"images/{temp_filename}"
        s3_client.upload_file(
            temp_filename, "musse.ai", s3_key, ExtraArgs={"ContentType": "image/png"}
        )

        os.remove(temp_filename)

        # s3_url = f"![Generated Image {i+1}](https://musse.ai/{s3_key})"
        s3_url = f"\n<img src='https://musse.ai/{s3_key}'>"
        result_urls.append(s3_url)

    return result_urls


tools = [
    gen_images,
    # generate_social_media_image,
    # gen_images_2
]
