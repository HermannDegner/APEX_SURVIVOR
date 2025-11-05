"""
ANSI color codes for terminal display
"""


class Colors:
    """ANSI色定義"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    @classmethod
    def get_color(cls, color_name: str) -> str:
        """色名からANSIコードを取得"""
        return getattr(cls, color_name.upper(), cls.RESET)
