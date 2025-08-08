"""
Split markdown content into chunks while preserving formatting and sentence structure.
"""

import re
import textwrap


def truncate(text: str, max_length: int = 1900) -> list[str]:
    """Split text into chunks while preserving markdown and sentence structure.
    
    Args:
        text: The text to split
        max_length: Maximum length of each chunk
        
    Returns:
        List of text chunks that preserve formatting and readability
    """
    # If text is shorter than max_length, return it as a single chunk
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = ""

    # Split into paragraphs first (preserves markdown block structure)
    paragraphs = text.split('\n\n')

    for paragraph in paragraphs:
        # If adding this paragraph would exceed max_length
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            # If current_chunk is not empty, add it to chunks
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = ""

            # If paragraph itself is too long, split it into sentences
            if len(paragraph) > max_length:
                sentences = re.split(r'([.!?]+\s+)', paragraph)
                temp_chunk = ""

                for sentence in sentences:
                    if len(temp_chunk) + len(sentence) > max_length:
                        if temp_chunk:
                            chunks.append(temp_chunk.strip())
                        temp_chunk = sentence
                    else:
                        temp_chunk += sentence

                # If we still have an oversized chunk (no sentence breaks), force split
                if temp_chunk and len(temp_chunk) > max_length:
                    while len(temp_chunk) > max_length:
                        chunks.append(temp_chunk[:max_length].strip())
                        temp_chunk = temp_chunk[max_length:]
                    if temp_chunk:
                        current_chunk = temp_chunk
                elif temp_chunk:
                    current_chunk = temp_chunk
            else:
                current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n"
            current_chunk += paragraph

    # Add the last chunk if there is one
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


if __name__ == "__main__":
    SAMPLE = textwrap.dedent("""
        # Stable Diffusion 3.5: Is It Flux's Rival? Latent Vision's Deep Dive & Community Call to Action
        ## Summary
        The video is a review and exploration of the newly released Stable Diffusion 3.5 Large model by Latent Vision, a prominent figure in the AI art generation community. Here's a breakdown of what happened:

        **Key Highlights:**

        * **SD 3.5 Release:** The video announces the upcoming release of Stable Diffusion 3.5 Large, along with plans for Medium and Turbo versions.
        * **Initial Impressions:** Latent Vision expresses that SD 3.5 is good, but not a competitor to Flux, another popular model.  Its strengths lie in aesthetics, styles, and prompt understanding.
        * **Technical Deep Dive:**
            *  The video covers model loading, memory usage, negative prompting, samplers, schedulers, and CFG (classifier free guidance) settings.
            * It demonstrates the model's capabilities through various examples, including generating portraits of different ethnicities, artistic styles (impasto, watercolor, charcoal, anime), and complex scenes.
        * **Overfitting Issues:** Latent Vision points out that SD 3.5 seems overfit on realistic portraits, resulting in overly smooth faces even when aiming for textured styles. He addresses this by manipulating text encoder block weights and introducing a "FluxModelBlocksBuster" node to adjust model block weights.
        * **Prompt Comprehension and Bleeding:** The model showcases impressive prompt comprehension, especially when generating images with mixed styles (e.g., photorealistic man with an anime woman). Latent Vision analyzes successful prompt structures and emphasizes the importance of defining factors and efficient token usage.
        * **Limitations:** Despite its strengths, SD 3.5 struggles with hands, feet, anatomy, and object interaction. It also has limitations with resolution (around 1 megapixel).
        * **Potential as a Base Model:** Latent Vision believes SD 3.5 has strong potential as a base model for future development and fine-tuning, comparing it to the evolution of SD 1.5 and SDXL.  He emphasizes the need for community effort in training and developing tools like IP adapters and ControlNets. 
        * **Call to Action:** He urges viewers to participate in the open-source development of SD 3.5 to create alternatives to closed-source cloud services.
        * **Turbo Model:** The video briefly discusses the upcoming SD 3.5 Turbo model, highlighting its speed and suggesting optimal settings for better results.
        * **New Project Announcement:** Latent Vision reveals his work on a new UI for Diffusers, a versatile AI library, aiming to provide a more user-friendly interface for its capabilities.


        **Overall, the video serves as both a review and a tutorial, showcasing the strengths and weaknesses of SD 3.5 while also providing technical insights and encouraging community involvement in its future development. It highlights the potential of SD 3.5 as a powerful and flexible base model for the AI art generation community.**

        ## Hot Takes
        ## 5 Hottest Takes from the Stable Diffusion 3.5 Review:

        1. **"It's not remotely comparable to Flux, but that's not the point."** (00:00:10) - This immediately sets a controversial tone, comparing the newly released SD 3.5 to the popular Flux model and suggesting it's inferior, but then dismissing the comparison as irrelevant. It sparks debate on the true capabilities and potential of SD 3.5.

        2. **"The model itself is about 16GB at FP16 and 8GB at FP8."** (00:01:35) - While seemingly a factual statement, this highlights the high resource requirements of SD 3.5, potentially excluding users with less powerful hardware and raising concerns about accessibility and inclusivity within the AI art community.

        3. **"And of course it's very good at anime and that's how we know that Lycon is involved in the training."** (00:05:12) - This is a speculative and somewhat accusatory statement, implying Lycon's involvement in the training process based solely on the model's proficiency in generating anime-style images. It can be seen as controversial due to its lack of concrete evidence and potential implications for the model's biases.

        4. **"We might be lucky here, because if true, we will be able to get some decent IEP adapter for SD3.5."** (00:07:56) - This expresses hope for developing InstructPix2Pix (IEP) adapters for SD 3.5 based on its unique architecture. It ignites discussion on the possibilities of fine-tuning and adapting the model for specific tasks and workflows, potentially surpassing existing models in certain areas.

        5. **"I won't hide that the future of open source or at least local AI generation is at risk."** (00:14:44) - This is a bold statement expressing concern about the future of open-source AI and advocating for the development of models that allow local training. It fuels the debate on the balance between open-source initiatives and commercial cloud services, and the potential implications for accessibility and innovation in the AI art space.
        """).strip()

    print(truncate(SAMPLE))
