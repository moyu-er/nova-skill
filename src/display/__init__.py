"""
Display module - Progress display and terminal UI
"""
from .progress import (
    Colors,
    DisplayConfig,
    ProgressDisplay,
    SimpleProgressDisplay,
)

# Rich-based UI components (optional, requires rich>=13.0.0)
try:
    from .rich_ui import (
        TaskSidebar,
        RichProgressDisplay,
        SimpleRichDisplay,
    )
    _rich_available = True
except ImportError:
    _rich_available = False
    TaskSidebar = None
    RichProgressDisplay = None
    SimpleRichDisplay = None

__all__ = [
    'Colors',
    'DisplayConfig',
    'ProgressDisplay',
    'SimpleProgressDisplay',
    'TaskSidebar',
    'RichProgressDisplay',
    'SimpleRichDisplay',
]

# Version info
def is_rich_available() -> bool:
    """Check if rich library is available"""
    return _rich_available
