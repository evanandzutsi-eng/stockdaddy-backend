from datetime import datetime
from typing import List

def generate_line_chart_svg(
    symbol: str,
    timestamps: List[datetime],
    prices: List[float],
    width: int = 800,
    height: int = 400
) -> bytes:
    """
    Pure-Python SVG generator. 
    Zero external dependencies (no matplotlib/plotly), ensuring a tiny 
    Docker image footprint and sub-millisecond rendering times.
    """
    if not timestamps or not prices:
        return b"<svg xmlns='http://www.w3.org/2000/svg' width='100' height='50'><text x='10' y='30'>No Data</text></svg>"

    min_price = min(prices)
    max_price = max(prices)
    price_range = max_price - min_price if max_price != min_price else 1.0
    
    padding = 40
    chart_width = width - (2 * padding)
    chart_height = height - (2 * padding)
    
    # Map data points to SVG coordinates
    points = []
    for i, ts in enumerate(timestamps):
        x = padding + (i / (len(timestamps) - 1)) * chart_width if len(timestamps) > 1 else padding
        y = padding + chart_height - ((prices[i] - min_price) / price_range) * chart_height
        points.append(f"{x:.2f},{y:.2f}")
        
    path_d = "M " + " L ".join(points)
    
    # Construct clean, lightweight SVG markup
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
    <rect width="100%" height="100%" fill="#ffffff"/>
    <text x="{width/2}" y="20" font-family="Arial, sans-serif" font-size="16" font-weight="bold" text-anchor="middle" fill="#333333">{symbol} Price Chart</text>
    <text x="{padding}" y="{height - 10}" font-family="Arial, sans-serif" font-size="12" fill="#666666">₦{min_price:,.2f}</text>
    <text x="{width - padding}" y="{height - 10}" font-family="Arial, sans-serif" font-size="12" fill="#666666" text-anchor="end">₦{max_price:,.2f}</text>
    <path d="{path_d}" fill="none" stroke="#00A859" stroke-width="2" stroke-linejoin="round"/>
</svg>"""
    return svg.encode('utf-8')