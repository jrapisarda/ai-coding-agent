import openai
import os
from typing import Optional, Dict, Any
from ..shared.config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

class OpenAIClient:
    def __init__(self):
        self.client = openai.AsyncOpenAI()
    
    async def generate_content(
        self,
        title: str,
        brief: str,
        language: str = "en",
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Generate content using OpenAI GPT"""
        try:
            prompt = f"""
            Create engaging content based on the following requirements:
            
            Title: {title}
            Brief: {brief}
            Language: {language}
            
            The content should be:
            - Professional and engaging
            - Appropriate for outreach and storytelling
            - Optimized for the target audience
            - Clear and concise
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional content creator specializing in outreach and storytelling."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"Failed to generate content: {str(e)}")
    
    async def translate_content(
        self,
        content: str,
        target_language: str,
        source_language: str = "auto"
    ) -> str:
        """Translate content using OpenAI"""
        try:
            prompt = f"""
            Translate the following content to {target_language}:
            
            Content: {content}
            
            Please provide a natural, professional translation that maintains the original meaning and tone.
            """
            
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional translator specializing in business and outreach content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"Failed to translate content: {str(e)}")
    
    async def moderate_content(self, content: str) -> Dict[str, Any]:
        """Check content for appropriateness"""
        try:
            response = await self.client.moderations.create(
                input=content
            )
            
            return {
                "is_appropriate": not response.results[0].flagged,
                "categories": response.results[0].categories,
                "scores": response.results[0].category_scores
            }
            
        except Exception as e:
            return {
                "is_appropriate": True,
                "error": str(e)
            }