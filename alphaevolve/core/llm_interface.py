import logging
import os
import time
from typing import Dict, List, Optional, Any, Union
import asyncio
import json

# Import litellm for handling different LLM providers
try:
    from litellm import completion
    has_litellm = True
except ImportError:
    has_litellm = False

logger = logging.getLogger(__name__)

class LLMInterface:
    """
    Interface to communicate with Large Language Models.
    Supports multiple LLM providers through litellm.
    """
    
    def __init__(
        self,
        model: str = "lm_studio/llama-3-8b-instruct",
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        timeout: int = 60,
        retry_attempts: int = 3,
        retry_delay: int = 5,
        fallback_models: Optional[List[str]] = None,
    ):
        """
        Initialize the LLM interface.
        
        Args:
            model: LLM model identifier (e.g., "lm_studio/llama-3-8b-instruct")
            api_key: API key for the LLM service (optional)
            api_base: Base URL for the LLM API (optional)
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens to generate
            timeout: Timeout for API calls in seconds
            retry_attempts: Number of retry attempts on failure
            retry_delay: Delay between retries in seconds
            fallback_models: List of models to try if primary model fails
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.fallback_models = fallback_models or []
        
        # Track usage statistics
        self.call_count = 0
        self.total_tokens = 0
        self.failed_calls = 0
        
        # Check if litellm is available
        if not has_litellm:
            logger.warning("litellm not found. Please install it with 'pip install litellm'")
        
        # Set up environment variables for litellm
        if api_base and "lm_studio" in model.lower():
            os.environ["LM_STUDIO_API_BASE"] = api_base
        
        # Configure API keys in environment variables
        if api_key:
            if "openai" in model.lower():
                os.environ["OPENAI_API_KEY"] = api_key
            elif "anthropic" in model.lower():
                os.environ["ANTHROPIC_API_KEY"] = api_key
            # Add more providers as needed
        
    async def generate(self, prompt: str) -> str:
        """
        Generate text from a prompt using the configured LLM.
        
        Args:
            prompt: Input prompt to send to the LLM
            
        Returns:
            Generated text from the LLM
        """
        self.call_count += 1
        
        # Try primary model with retries
        for attempt in range(self.retry_attempts):
            try:
                response = await self._call_llm(self.model, prompt)
                return response
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}/{self.retry_attempts}): {str(e)}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
        
        # Try fallback models if primary model fails
        self.failed_calls += 1
        for fallback_model in self.fallback_models:
            try:
                logger.info(f"Trying fallback model: {fallback_model}")
                response = await self._call_llm(fallback_model, prompt)
                return response
            except Exception as e:
                logger.warning(f"Fallback LLM call failed ({fallback_model}): {str(e)}")
        
        # If all attempts fail
        raise RuntimeError(f"All LLM calls failed after {self.retry_attempts} attempts and {len(self.fallback_models)} fallback models")
    
    async def _call_llm(self, model: str, prompt: str) -> str:
        """
        Make the actual call to the LLM API.
        
        Args:
            model: Model identifier
            prompt: Input prompt
            
        Returns:
            Generated text
        """
        if not has_litellm:
            raise ImportError("litellm is required but not installed")
        
        messages = [{"role": "user", "content": prompt}]
        
        # Call the model using litellm
        try:
            response = completion(
                model=model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout
            )
            
            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                self.total_tokens += response.usage.get('total_tokens', 0)
            
            # Extract and return the generated text
            if hasattr(response, 'choices') and response.choices:
                return response.choices[0].message.content
            else:
                logger.warning(f"Unexpected response format: {response}")
                return str(response)
                
        except Exception as e:
            logger.error(f"Error calling LLM: {str(e)}")
            raise
            
    async def batch_generate(self, prompts: List[str], max_concurrent: int = 5) -> List[str]:
        """
        Generate responses for multiple prompts in parallel.
        
        Args:
            prompts: List of prompts to send to the LLM
            max_concurrent: Maximum number of concurrent requests
            
        Returns:
            List of generated responses
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _generate_with_semaphore(prompt):
            async with semaphore:
                return await self.generate(prompt)
        
        tasks = [_generate_with_semaphore(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks, return_exceptions=True)
        
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for the LLM interface."""
        return {
            "call_count": self.call_count,
            "total_tokens": self.total_tokens,
            "failed_calls": self.failed_calls,
            "success_rate": (self.call_count - self.failed_calls) / max(1, self.call_count)
        }
        
    async def validate_connection(self) -> bool:
        """Test the connection to the LLM API."""
        try:
            test_response = await self.generate("Hello, this is a test message to verify the LLM connection is working.")
            return bool(test_response)
        except Exception as e:
            logger.error(f"Connection validation failed: {str(e)}")
            return False 