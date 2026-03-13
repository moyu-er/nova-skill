"""
Time Tools - Date and time utilities
"""
from datetime import datetime
from typing import Annotated, Optional
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import tool


@tool
def get_current_time(timezone: Annotated[Optional[str], "Timezone (e.g., 'America/New_York', 'Asia/Shanghai'). Uses system timezone if not specified."] = None) -> str:
    """Get current time with optional timezone specification"""
    try:
        if timezone:
            try:
                tz = ZoneInfo(timezone)
                now = datetime.now(tz)
                return f"Current time in {timezone}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\nUTC offset: {now.strftime('%z')}"
            except Exception:
                return f"Invalid timezone: {timezone}. Use /timezones to see available options."
        else:
            now = datetime.now()
            return f"Current local time: {now.strftime('%Y-%m-%d %H:%M:%S')}"
    except Exception as e:
        return f"Error getting time: {e}"


@tool
def list_timezones(region: Annotated[Optional[str], "Filter by region prefix (e.g., 'America', 'Europe', 'Asia'). Shows all if not specified."] = None) -> str:
    """List available timezones, optionally filtered by region"""
    try:
        all_zones = sorted(available_timezones())

        if region:
            filtered = [z for z in all_zones if z.startswith(region)]
            if not filtered:
                return f"No timezones found for region: {region}"
            zones = filtered
            header = f"Timezones in {region} ({len(zones)} found):"
        else:
            # Show common timezones if no filter
            common_prefixes = ['America', 'Europe', 'Asia', 'Pacific', 'Africa']
            zones = [z for z in all_zones if any(z.startswith(p) for p in common_prefixes)]
            header = f"Common timezones ({len(zones)} shown, use region parameter to filter):"

        # Group by region
        by_region = {}
        for zone in zones:
            region_name = zone.split('/')[0]
            if region_name not in by_region:
                by_region[region_name] = []
            by_region[region_name].append(zone)

        lines = [header, ""]
        for region_name in sorted(by_region.keys()):
            lines.append(f"{region_name}:")
            for zone in by_region[region_name][:5]:  # Show first 5 per region
                lines.append(f"  - {zone}")
            if len(by_region[region_name]) > 5:
                lines.append(f"  ... and {len(by_region[region_name]) - 5} more")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Error listing timezones: {e}"
