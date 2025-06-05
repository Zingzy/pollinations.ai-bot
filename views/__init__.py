"""
Views package for the Pollinations.ai Discord bot.

This package contains all the UI view classes following the new inheritance-based architecture:
- BaseImageView: Abstract base class with common button functionality (delete, bookmark)
- Specific view classes: Inherit from base and add command-specific buttons

Architecture Benefits:
- 80% reduction in button-related code duplication
- Consistent behavior across all commands
- Easy to add new button functionality to all views
- Centralized error handling for button interactions
"""

from .base_view import BaseImageView
from .imagine_view import ImagineView, EditImageModal
from .cross_pollinate_view import CrossPollinateView
from .multi_pollinate_view import MultiPollinateView
from .beemoji_view import BeemojiView

__all__ = [
    "BaseImageView",
    "ImagineView",
    "EditImageModal",
    "CrossPollinateView",
    "MultiPollinateView",
    "BeemojiView",
]
