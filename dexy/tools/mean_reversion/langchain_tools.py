"""
LangChain tools for cryptocurrency technical analysis and mean reversion strategies.
This module provides a set of tools that can be used with LangChain agents to analyze
cryptocurrency price data and identify mean reversion opportunities.
"""

from typing import Dict, List, Optional, Union, Tuple, Any
from pydantic import BaseModel, Field
from datetime import datetime

from langchain_core.tools import tool, ToolException

from tools.mean_reversion.core.api import TokenPriceAPI
from tools.mean_reversion.core.indicators import MeanReversionIndicators, MeanReversionService

# Parameter models for improved documentation and validation


class IndicatorParams(BaseModel):
    """Parameters for technical indicator calculations."""

    token_id: str = Field(
        description="The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')"
    )
    window: int = Field(
        default=20,
        description="The lookback window for indicator calculations (in days)",
    )
    num_std: float = Field(
        default=2.0, description="Number of standard deviations for Bollinger Bands"
    )


class HistoricalDataParams(BaseModel):
    """Parameters for historical data fetching."""

    token_id: str = Field(
        description="The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')"
    )
    days: int = Field(
        default=30, description="Number of days of historical data to fetch"
    )
    vs_currency: str = Field(default="usd", description="The currency to get prices in")


# LangChain Tools


@tool
def get_token_price(token_id: str) -> float:
    """
    Get the current price of a cryptocurrency token in USD.

    Args:
        token_id: The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')

    Returns:
        The current price of the token in USD.
    """
    api = TokenPriceAPI()
    try:
        return api.get_price(token_id)
    except Exception as e:
        raise ToolException(f"Error fetching price for {token_id}: {str(e)}")


@tool
def get_token_z_score(token_id: str, window: int = 20) -> float:
    """
    Calculate the Z-score for a token to determine how many standard deviations
    the current price is from the moving average.

    Args:
        token_id: The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')
        window: The number of days to use for calculating the moving average and standard deviation (default: 20)

    Returns:
        The Z-score value. Positive values indicate the price is above the mean,
        negative values indicate it's below the mean.
    """
    api = TokenPriceAPI()
    indicators = MeanReversionIndicators()
    try:
        prices, _ = api.get_historical_prices(token_id, days=max(30, window * 2))
        return indicators.calculate_z_score(prices, window=window)
    except Exception as e:
        raise ToolException(f"Error calculating Z-score for {token_id}: {str(e)}")


@tool
def get_token_rsi(token_id: str, window: int = 14) -> float:
    """
    Calculate the Relative Strength Index (RSI) for a token.

    Args:
        token_id: The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')
        window: The number of days to use for the RSI calculation (default: 14)

    Returns:
        The RSI value (0-100). Values above 70 generally indicate overbought conditions,
        while values below 30 indicate oversold conditions.
    """
    api = TokenPriceAPI()
    indicators = MeanReversionIndicators()
    try:
        prices, _ = api.get_historical_prices(token_id, days=max(30, window * 2))
        return indicators.calculate_rsi(prices, window=window)
    except Exception as e:
        raise ToolException(f"Error calculating RSI for {token_id}: {str(e)}")


@tool(response_format="content_and_artifact")
def get_token_bollinger_bands(
    token_id: str, window: int = 20, num_std: float = 2.0
) -> Tuple[str, Dict[str, Any]]:
    """
    Calculate Bollinger Bands for a token and determine if it's in a mean reversion zone.

    Args:
        token_id: The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')
        window: The number of days to use for calculations (default: 20)
        num_std: Number of standard deviations for the bands (default: 2.0)

    Returns:
        Analysis of the token's position relative to Bollinger Bands and mean reversion potential.
    """
    api = TokenPriceAPI()
    indicators = MeanReversionIndicators()
    try:
        prices, dates = api.get_historical_prices(token_id, days=max(30, window * 2))

        bb_data = indicators.calculate_bollinger_bands(
            prices, window=window, num_std=num_std
        )

        # Prepare analysis message
        current_price = bb_data["current_price"]
        upper_band = bb_data["upper_band"]
        lower_band = bb_data["lower_band"]
        percent_b = bb_data["percent_b"]

        interpretation = indicators.interpret_bb(percent_b)

        message = f"""
Token: {token_id.upper()}
Current Price: ${current_price:.2f}
Bollinger Bands (window: {window}, std: {num_std}):
- Upper Band: ${upper_band:.2f}
- Middle Band: ${bb_data["middle_band"]:.2f}
- Lower Band: ${lower_band:.2f}
Percent B: {percent_b:.2f}

Analysis: {interpretation}
"""

        # Return both the text message and the data as artifact
        return message, {
            "token_id": token_id,
            "data": bb_data,
            "dates": dates,
            "prices": prices,
            "percent_b": percent_b,
        }
    except Exception as e:
        raise ToolException(
            f"Error calculating Bollinger Bands for {token_id}: {str(e)}"
        )


@tool
def get_token_indicators(token_id: str, window: int = 20) -> str:
    """
    Get comprehensive technical indicators for a cryptocurrency token.

    Args:
        token_id: The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')
        window: The lookback window for calculations (default: 20)

    Returns:
        A detailed analysis of the token's technical indicators.
    """
    service = MeanReversionService()
    try:
        metrics = service.get_all_metrics(
            token_id,
            days=max(30, window * 2),
            z_window=window,
            rsi_window=window,
            bb_window=window,
        )

        z_score = metrics["metrics"]["z_score"]["value"]
        z_interpretation = metrics["metrics"]["z_score"]["interpretation"]

        rsi = metrics["metrics"]["rsi"]["value"]
        rsi_interpretation = metrics["metrics"]["rsi"]["interpretation"]

        bb = metrics["metrics"]["bollinger_bands"]

        return f"""
=== TECHNICAL INDICATORS FOR {token_id.upper()} ===
Current Price: ${metrics["current_price"]:.2f}
Timestamp: {metrics["timestamp"]}

Z-SCORE: {z_score:.2f}
- Interpretation: {z_interpretation}
- Measures how many standard deviations the price is from its {window}-day mean

RSI: {rsi:.2f}
- Interpretation: {rsi_interpretation}
- Values above 70 generally indicate overbought conditions
- Values below 30 generally indicate oversold conditions

BOLLINGER BANDS:
- Upper Band: ${bb["upper_band"]:.2f}
- Middle Band: ${bb["middle_band"]:.2f}
- Lower Band: ${bb["lower_band"]:.2f}
- Percent B: {bb["percent_b"]:.2f}
- Position: {bb["interpretation"]}

NOTE: This analysis is based on historical data and should not be considered financial advice.
"""
    except Exception as e:
        raise ToolException(f"Error calculating indicators for {token_id}: {str(e)}")


@tool(response_format="content_and_artifact")
def get_advanced_indicators(
    token_id: str, window: int = 20
) -> Tuple[str, Dict[str, Any]]:
    """
    Get technical indicators with both human-readable analysis and structured data.

    Args:
        token_id: The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')
        window: The lookback window for calculations (default: 20)

    Returns:
        Both an analysis message and structured data for downstream processing.
    """
    service = MeanReversionService()
    try:
        indicators = service.get_all_metrics(
            token_id,
            days=max(30, window * 2),
            z_window=window,
            rsi_window=window,
            bb_window=window,
        )

        z_score = indicators["metrics"]["z_score"]["value"]
        z_signal = indicators["metrics"]["z_score"]["interpretation"]
        rsi = indicators["metrics"]["rsi"]["value"]
        rsi_signal = indicators["metrics"]["rsi"]["interpretation"]
        bb_data = indicators["metrics"]["bollinger_bands"]
        bb_signal = bb_data["interpretation"]

        # Determine overall signal
        signals = [z_signal, rsi_signal, bb_signal]
        bullish_signals = sum(1 for s in signals if "UPWARD" in s)
        bearish_signals = sum(1 for s in signals if "DOWNWARD" in s)

        if bullish_signals > bearish_signals:
            overall_sentiment = "BULLISH"
        elif bearish_signals > bullish_signals:
            overall_sentiment = "BEARISH"
        else:
            overall_sentiment = "NEUTRAL"

        message = f"""
=== TECHNICAL ANALYSIS FOR {token_id.upper()} ===
Current Price: ${indicators["current_price"]:.2f}

INDICATOR SUMMARY:
- Z-Score: {z_score:.2f} ({z_signal})
- RSI: {rsi:.2f} ({rsi_signal})
- Bollinger %B: {bb_data["percent_b"]:.2f} ({bb_signal})

OVERALL SENTIMENT: {overall_sentiment}

This analysis combines multiple technical indicators to provide a comprehensive view
of the token's current market position. Remember that all technical analysis is based
on historical patterns and does not guarantee future performance.
"""

        # Return both the message and the full data as artifact
        return message, indicators
    except Exception as e:
        raise ToolException(f"Error calculating indicators for {token_id}: {str(e)}")


@tool
def get_historical_indicators(token_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get historical indicators for a token over a specified time period.

    Args:
        token_id: The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')
        days: Number of days of historical data to fetch

    Returns:
        A dictionary containing historical price data and calculated indicators
    """
    try:
        service = MeanReversionService()
        return service.get_historical_indicators(token_id, days)
    except Exception as e:
        raise ToolException(
            f"Data not available or insufficient price history. Try a different token or time window. Error: {str(e)}"
        )


@tool
def mean_reversion_analyzer(token_id: str) -> str:
    """
    Comprehensive mean reversion analysis for a cryptocurrency token.
    This tool combines multiple technical indicators to provide a holistic view.

    Args:
        token_id: The ID of the token (e.g., 'bitcoin', 'ethereum', 'solana')

    Returns:
        A comprehensive analysis of the token's mean reversion potential.
    """
    service = MeanReversionService()
    try:
        # Get all metrics with default settings
        metrics = service.get_all_metrics(token_id)

        # Extract key values
        current_price = metrics["current_price"]

        z_score = metrics["metrics"]["z_score"]["value"]
        z_signal = metrics["metrics"]["z_score"]["interpretation"]

        rsi = metrics["metrics"]["rsi"]["value"]
        rsi_signal = metrics["metrics"]["rsi"]["interpretation"]

        bb_data = metrics["metrics"]["bollinger_bands"]
        bb_signal = bb_data["interpretation"]
        percent_b = bb_data["percent_b"]

        # Combine signals for overall recommendation
        signals = [z_signal, rsi_signal, bb_signal]
        upward_signals = sum(1 for s in signals if "UPWARD" in s)
        downward_signals = sum(1 for s in signals if "DOWNWARD" in s)

        overall_signal = "NEUTRAL"
        if upward_signals > downward_signals:
            overall_signal = "POTENTIAL UPWARD REVERSION"
        elif downward_signals > upward_signals:
            overall_signal = "POTENTIAL DOWNWARD REVERSION"

        # Format the message
        message = f"""
=== MEAN REVERSION ANALYSIS FOR {token_id.upper()} ===
Based on the last 30 days of price data

Current Price: ${current_price:.2f}

TECHNICAL INDICATORS:
1. Z-Score: {z_score:.2f} - {z_signal}
   (Measures how many standard deviations the price is from its mean)

2. RSI: {rsi:.2f} - {rsi_signal}
   (Measures the speed and change of price movements, range 0-100)

3. Bollinger Bands:
   - Upper Band: ${bb_data["upper_band"]:.2f}
   - Middle Band: ${bb_data["middle_band"]:.2f}
   - Lower Band: ${bb_data["lower_band"]:.2f}
   - Percent B: {percent_b:.2f} - {bb_signal}
   (Measures price relative to Bollinger Bands)

OVERALL SIGNAL: {overall_signal}

Note: This analysis is based on mean reversion principles using historical data.
Mean reversion strategies assume that prices tend to move back toward their mean over time.
"""
        return message
    except Exception as e:
        raise ToolException(f"Error analyzing token {token_id}: {str(e)}")

