"""
calculator.py
─────────────
Painting quote calculator. All rates are in Indian Rupees (₹).
Wall area formula: 2*(L+W)*H * 0.85 (15% deduction for doors/windows)
GST is 18% on the subtotal.
"""

import math

PAINT_RATES: dict = {
    "economy": {
        "paint_per_ltr": 180,
        "coverage_per_ltr": 120,
        "coats": 2,
        "name": "Economy",
        "description": "Basic finish, 2-year durability",
    },
    "premium": {
        "paint_per_ltr": 350,
        "coverage_per_ltr": 100,
        "coats": 2,
        "name": "Premium",
        "description": "Smooth finish, 5-year durability",
    },
    "luxury": {
        "paint_per_ltr": 650,
        "coverage_per_ltr": 90,
        "coats": 2,
        "name": "Luxury",
        "description": "Designer finish, 7-year durability",
    },
}

LABOR_RATE_PER_SQFT       = 12   # ₹/sq ft
PUTTY_RATE_PER_SQFT       = 8    # ₹/sq ft
PRIMER_RATE_PER_SQFT      = 5    # ₹/sq ft
MOLDING_RATE_PER_FT       = 45   # ₹/linear ft
FALSE_CEILING_RATE_PER_SQFT = 85 # ₹/sq ft
GST_RATE                  = 0.18 # 18%


def calculate_quote(rooms: list, paint_grade: str, extras: dict) -> dict:
    """
    Calculate a complete painting quote.

    Returns a dict with:
        total_area, paint_cost, labor_cost, extras_cost,
        gst_cost, total_cost, breakdown (ordered dict), room_details,
        paint_needed_liters, subtotal
    """
    paint_info = PAINT_RATES.get(paint_grade, PAINT_RATES["premium"])

    total_area   = 0.0
    ceiling_total = 0.0
    room_details = []

    for i, room in enumerate(rooms):
        length = float(room.get("length", 0))
        width  = float(room.get("width",  0))
        height = float(room.get("height", 10))

        wall_area    = 2 * (length + width) * height * 0.85
        ceiling_area = length * width
        room_total   = wall_area + ceiling_area
        total_area   += room_total
        ceiling_total += ceiling_area

        room_details.append({
            "name":       room.get("name", f"Room {i + 1}"),
            "dimensions": f"{length:.0f}×{width:.0f}×{height:.0f} ft",
            "wall_area":  round(wall_area, 2),
            "ceiling_area": round(ceiling_area, 2),
            "area":       round(room_total, 2),
        })

    # Paint
    paint_needed = (total_area / paint_info["coverage_per_ltr"]) * paint_info["coats"]
    paint_cost   = paint_needed * paint_info["paint_per_ltr"]

    # Labor
    labor_cost = total_area * LABOR_RATE_PER_SQFT

    # Extras
    extras_cost      = 0.0
    extras_breakdown: dict = {}

    if extras.get("putty"):
        c = total_area * PUTTY_RATE_PER_SQFT
        extras_cost += c
        extras_breakdown["Wall Putty"] = round(c, 2)

    if extras.get("primer"):
        c = total_area * PRIMER_RATE_PER_SQFT
        extras_cost += c
        extras_breakdown["Primer Coat"] = round(c, 2)

    if extras.get("molding"):
        molding_length = float(extras.get("molding_length", 0))
        c = molding_length * MOLDING_RATE_PER_FT
        extras_cost += c
        extras_breakdown["Crown Molding"] = round(c, 2)

    if extras.get("false_ceiling"):
        c = ceiling_total * FALSE_CEILING_RATE_PER_SQFT
        extras_cost += c
        extras_breakdown["False Ceiling"] = round(c, 2)

    subtotal  = paint_cost + labor_cost + extras_cost
    gst_cost  = subtotal * GST_RATE
    total_cost = subtotal + gst_cost

    grade_label = paint_info["name"]
    breakdown = {
        f"Paint ({grade_label})": round(paint_cost, 2),
        "Labour":                 round(labor_cost, 2),
        **extras_breakdown,
        "Subtotal":               round(subtotal, 2),
        "GST (18%)":              round(gst_cost, 2),
        "Grand Total":            round(total_cost, 2),
    }

    return {
        "total_area":          round(total_area, 2),
        "paint_cost":          round(paint_cost, 2),
        "labor_cost":          round(labor_cost, 2),
        "extras_cost":         round(extras_cost, 2),
        "gst_cost":            round(gst_cost, 2),
        "subtotal":            round(subtotal, 2),
        "total_cost":          round(total_cost, 2),
        "breakdown":           breakdown,
        "room_details":        room_details,
        "paint_needed_liters": round(paint_needed, 2),
        "paint_grade_info":    paint_info,
    }
