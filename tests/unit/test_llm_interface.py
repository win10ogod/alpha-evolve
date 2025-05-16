"""
Unit tests for the llm_interface module.
"""

import pytest
from unittest.mock import patch, MagicMock
import asyncio
from alphaevolve.core.llm_interface import LLMInterface

class TestLLMInterface:
    """Tests for the LLMInterface class."""
    
    @patch('alphaevolve.core.llm_interface.completion')
    @pytest.mark.asyncio
    async def test_generate(self, mock_completion):
        """Test generating text using the LLM."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated response"
        mock_response.usage = {"total_tokens": 50}
        mock_completion.return_value = mock_response
        
        # Create LLM interface
        llm = LLMInterface(
            model="test-model",
            temperature=0.5,
            max_tokens=100
        )
        
        # Generate text
        response = await llm.generate("Test prompt")
        
        # Verify the response
        assert response == "Generated response"
        
        # Verify the call to the LLM API
        mock_completion.assert_called_once()
        args, kwargs = mock_completion.call_args
        assert kwargs["model"] == "test-model"
        assert kwargs["temperature"] == 0.5
        assert kwargs["max_tokens"] == 100
        assert kwargs["messages"][0]["content"] == "Test prompt"
        
        # Verify usage tracking
        assert llm.call_count == 1
        assert llm.total_tokens == 50
    
    @patch('alphaevolve.core.llm_interface.completion')
    @pytest.mark.asyncio
    async def test_retry_on_error(self, mock_completion):
        """Test retry mechanism when LLM call fails."""
        # Setup mock to fail on first call, succeed on second
        mock_completion.side_effect = [
            Exception("LLM API error"),  # First call fails
            MagicMock(  # Second call succeeds
                choices=[MagicMock(message=MagicMock(content="Success after retry"))],
                usage={"total_tokens": 30}
            )
        ]
        
        # Create LLM interface with retry configuration
        llm = LLMInterface(
            model="test-model",
            retry_attempts=2,
            retry_delay=0.1  # Short delay for testing
        )
        
        # Generate text
        response = await llm.generate("Test prompt")
        
        # Verify the response
        assert response == "Success after retry"
        
        # Verify the LLM API was called twice
        assert mock_completion.call_count == 2
        
        # Verify usage tracking
        assert llm.call_count == 1  # Still counts as one logical call
        assert llm.total_tokens == 30
        assert llm.failed_calls == 0  # Not increased since retry succeeded
    
    @patch('alphaevolve.core.llm_interface.completion')
    @pytest.mark.asyncio
    async def test_all_retries_fail(self, mock_completion):
        """Test behavior when all retry attempts fail."""
        # Setup mock to always fail
        mock_completion.side_effect = Exception("LLM API error")
        
        # Create LLM interface with retry configuration but no fallbacks
        llm = LLMInterface(
            model="test-model",
            retry_attempts=2,
            retry_delay=0.1  # Short delay for testing
        )
        
        # Attempt to generate text
        with pytest.raises(RuntimeError) as exc_info:
            await llm.generate("Test prompt")
            
        # Verify error message
        assert "All LLM calls failed" in str(exc_info.value)
        
        # Verify the LLM API was called for all retry attempts
        assert mock_completion.call_count == 2
        
        # Verify usage tracking
        assert llm.call_count == 1  # Still counts as one logical call
        assert llm.failed_calls == 1
    
    @patch('alphaevolve.core.llm_interface.completion')
    @pytest.mark.asyncio
    async def test_fallback_model(self, mock_completion):
        """Test using a fallback model when primary model fails."""
        # Setup mock to fail with primary model, succeed with fallback
        mock_completion.side_effect = [
            Exception("Primary model error"),  # Primary model calls fail
            Exception("Primary model error again"),
            MagicMock(  # Fallback model succeeds
                choices=[MagicMock(message=MagicMock(content="Fallback model response"))],
                usage={"total_tokens": 40}
            )
        ]
        
        # Create LLM interface with fallback model
        llm = LLMInterface(
            model="primary-model",
            retry_attempts=2,
            retry_delay=0.1,
            fallback_models=["fallback-model"]
        )
        
        # Generate text
        response = await llm.generate("Test prompt")
        
        # Verify the response
        assert response == "Fallback model response"
        
        # Verify calls to the LLM API
        assert mock_completion.call_count == 3  # 2 primary + 1 fallback
        
        # Verify the last call used the fallback model
        last_call_args = mock_completion.call_args
        assert last_call_args[1]["model"] == "fallback-model"
        
        # Verify usage tracking
        assert llm.call_count == 1
        assert llm.total_tokens == 40
        assert llm.failed_calls == 1  # Increased since primary model failed
    
    @patch('alphaevolve.core.llm_interface.completion')
    @pytest.mark.asyncio
    async def test_batch_generate(self, mock_completion):
        """Test generating text for multiple prompts in parallel."""
        # Setup mock responses
        responses = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=f"Response {i}"))], 
                    usage={"total_tokens": 10 * (i+1)})
            for i in range(3)
        ]
        mock_completion.side_effect = responses
        
        # Create LLM interface
        llm = LLMInterface(model="test-model")
        
        # Generate text for multiple prompts
        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        results = await llm.batch_generate(prompts, max_concurrent=2)
        
        # Verify responses
        assert len(results) == 3
        assert "Response 0" in results
        assert "Response 1" in results
        assert "Response 2" in results
        
        # Verify calls to the LLM API
        assert mock_completion.call_count == 3
        
        # Verify usage tracking
        assert llm.call_count == 3
        assert llm.total_tokens == 60  # 10 + 20 + 30 