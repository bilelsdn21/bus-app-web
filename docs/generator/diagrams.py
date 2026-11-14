import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.dirname(os.path.abspath(__file__))
NAVY, GOLD, SKY, SLATE, GREEN = "#1a3a5c", "#f59e0b", "#e0f2fe", "#64748b", "#059669"


def box(ax, x, y, w, h, title, sub="", fill="white", edge=NAVY, tcolor=NAVY, fs=11):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=fill, ec=edge, lw=1.8))
    ax.text(x + w / 2, y + h * (0.62 if sub else 0.5), title, ha="center", va="center",
            fontsize=fs, fontweight="bold", color=tcolor)
    if sub:
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=fs - 2.5, color=SLATE)


def arrow(ax, p1, p2, label="", color=NAVY, style="-|>", rad=0.0, lx=0, ly=0.12):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=16, lw=1.8, color=color,
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((p1[0] + p2[0]) / 2 + lx, (p1[1] + p2[1]) / 2 + ly, label, ha="center", fontsize=8.5,
                color=color, fontweight="bold")


# ------------------------------------------------------------------ architecture
fig, ax = plt.subplots(figsize=(10, 6.0))
ax.set_xlim(-0.9, 10.2); ax.set_ylim(0.2, 6.2); ax.axis("off")

box(ax, 0.2, 4.7, 2.4, 1.0, "Utilisateurs", "téléphone · PC", fill=SKY)
box(ax, 0.2, 2.8, 2.4, 1.2, "Frontend React", "PWA · Vercel · CDN", fs=11)
box(ax, 0.2, 0.7, 2.4, 1.2, "Service Push", "navigateur (Google · Apple)", fill="#fef3c7", edge=GOLD, tcolor="#92400e")
box(ax, 3.9, 2.8, 2.6, 1.2, "API FastAPI", "Render · Francfort", fill="white")
ax.text(5.2, 2.95, "calculs · exports Excel · auth", ha="center", fontsize=7.5, color=SLATE)
box(ax, 7.8, 2.8, 2.2, 1.2, "PostgreSQL", "Supabase · Stockholm", fill="white", fs=10.5)
box(ax, 3.9, 4.7, 2.6, 1.0, "UptimeRobot", "ping /api/health", fill="#f1f5f9", edge=SLATE, tcolor=SLATE, fs=10)

arrow(ax, (1.4, 4.7), (1.4, 4.0), "HTTPS", lx=0.5, ly=0)
arrow(ax, (2.6, 3.7), (3.9, 3.7), "JSON + jeton", ly=0.1)
arrow(ax, (3.9, 3.1), (2.6, 3.1), "", ly=0)
arrow(ax, (6.5, 3.4), (7.8, 3.4), "SQL (SSL)", ly=0.12)
arrow(ax, (5.2, 4.7), (5.2, 4.0), "ping", color=SLATE, lx=0.35, ly=0)
arrow(ax, (3.9, 2.95), (2.6, 1.5), "Web Push", color=GOLD, lx=0.2, ly=-0.35)
arrow(ax, (0.2, 1.3), (0.2, 5.2), "alertes", color=GOLD, rad=-0.35, lx=-0.62, ly=0)
ax.text(4.55, 6.0, "Architecture technique — Bestimetravel Gestion des Bus", ha="center", fontsize=13, fontweight="bold", color=NAVY)
fig.savefig(os.path.join(OUT, "architecture.png"), dpi=170, bbox_inches="tight", facecolor="white")
plt.close(fig)

# ------------------------------------------------------------------ data model
fig, ax = plt.subplots(figsize=(10, 6.6))
ax.set_xlim(0, 10); ax.set_ylim(0, 6.6); ax.axis("off")


def entity(x, y, w, name, fields, fill="white", edge=NAVY):
    h = 0.42 + 0.27 * len(fields)
    ax.add_patch(FancyBboxPatch((x, y - h), w, h, boxstyle="round,pad=0.015,rounding_size=0.08", fc=fill, ec=edge, lw=1.6))
    ax.add_patch(FancyBboxPatch((x, y - 0.36), w, 0.36, boxstyle="round,pad=0.015,rounding_size=0.08", fc=edge, ec=edge, lw=1.6))
    ax.text(x + w / 2, y - 0.18, name, ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    for i, f in enumerate(fields):
        ax.text(x + 0.12, y - 0.36 - 0.2 - i * 0.27, f, ha="left", va="center", fontsize=8, color="#1e293b",
                fontfamily="DejaVu Sans Mono")
    return (x, y, w, h)


bus = entity(3.9, 6.3, 2.4, "buses", ["id (PK)", "name  · plate", "type  · region", "loyer · distance", "sort_order"], fill="#e0f2fe")
con = entity(0.1, 6.3, 2.7, "contracts", ["id (PK)", "bus_id (FK)", "start_date · end_date", "loyer · label"])
boo = entity(7.1, 6.3, 2.8, "bookings", ["id (PK)", "bus_id (FK)", "date · end_date", "type · destination", "heure_debut/fin", "client · pax · total"])
fue = entity(0.1, 3.7, 2.7, "fuel_months", ["id (PK)", "bus_id (FK)", "year · month", "estimated · actual"])
reg = entity(3.9, 3.7, 2.4, "region_periods", ["id (PK)", "bus_id (FK)", "region", "effective_from/to"])
des = entity(7.1, 3.9, 2.8, "destinations", ["id (PK)", "category · name", "price_micro", "price_otokar · price_bus"])
pri = entity(7.1, 1.8, 2.8, "price_periods", ["dest_name", "effective_from/to", "price_micro/otokar/bus"])
ren = entity(0.1, 1.75, 2.7, "rented_vehicles", ["id (PK)", "name · type · region", "start_date · end_date", "cost · notes"], fill="#fef3c7", edge="#b45309")
cfg = entity(3.9, 1.75, 2.4, "config", ["cut_morn (13h)", "cut_night (22h)", "current_prices_since"], fill="#f1f5f9", edge=SLATE)

for (x2, y2) in [(2.8, 5.6), (7.1, 5.6)]:
    pass
arrow(ax, (3.9, 5.55), (2.8, 5.55), "1—N", color=SLATE, style="-", lx=0, ly=0.1)
arrow(ax, (6.3, 5.55), (7.1, 5.55), "1—N", color=SLATE, style="-", lx=0, ly=0.1)
arrow(ax, (4.3, 4.65), (2.8, 3.3), "1—N", color=SLATE, style="-", lx=-0.2, ly=0.1)
arrow(ax, (5.1, 4.65), (5.1, 3.7), "1—N", color=SLATE, style="-", lx=0.3, ly=0)
arrow(ax, (8.5, 2.4), (8.5, 1.8), "par nom", color=SLATE, style="-", lx=0.45, ly=0)
ax.text(5.0, 6.55, "Modèle de données (PostgreSQL)", ha="center", fontsize=13, fontweight="bold", color=NAVY)
fig.savefig(os.path.join(OUT, "modele_donnees.png"), dpi=170, bbox_inches="tight", facecolor="white")
plt.close(fig)
print("diagrams ok")
