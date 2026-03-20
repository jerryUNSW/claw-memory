#!/usr/bin/env python3
"""
Experiment 1: Visualization Script

Generates publication-quality plots from experiment1 results.

Usage:
    python3 scripts/experiment1_plots.py
"""

import json
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

REPO_ROOT = Path(__file__).parent.parent
RESULTS_DIR = REPO_ROOT / "experiment1_results"
FIGURES_DIR = RESULTS_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'DejaVu Serif'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.05,
    'axes.linewidth': 0.8,
    'grid.linewidth': 0.5,
    'lines.linewidth': 1.5,
})

COLORS = {
    'hybrid': '#4C72B0',
    'semantic': '#DD8452',
    'hybrid_light': '#8FAFD4',
    'semantic_light': '#EEBB88',
    'minilm': '#55A868',
    'dpr': '#C44E52',
    'accent': '#8172B2',
    'grid': '#CCCCCC',
}


def load_results():
    path = RESULTS_DIR / "experiment1_results.json"
    if not path.exists():
        raise FileNotFoundError(f"Results not found: {path}. Run experiment1.py first.")
    with open(path) as f:
        return json.load(f)


def plot_main_comparison(results):
    """Figure 1: Main comparison bar chart — Recall@5 and Recall@10 across all conditions."""
    datasets = sorted(set(r['dataset'] for r in results))
    models = sorted(set(r['model'] for r in results))

    fig, axes = plt.subplots(1, len(datasets), figsize=(5 * len(datasets), 4.5), sharey=True)
    if len(datasets) == 1:
        axes = [axes]

    bar_width = 0.18
    metrics = ['recall_5', 'recall_10', 'mrr_10', 'hit_10']
    metric_labels = ['Recall@5', 'Recall@10', 'MRR@10', 'Hit@10']

    for ax_idx, ds in enumerate(datasets):
        ax = axes[ax_idx]
        ds_results = [r for r in results if r['dataset'] == ds]

        groups = []
        for model in models:
            hybrid = next((r for r in ds_results if r['model'] == model and 'Hybrid' in r['system']), None)
            semantic = next((r for r in ds_results if r['model'] == model and 'Semantic' in r['system']), None)
            if hybrid and semantic:
                groups.append((model, hybrid, semantic))

        x = np.arange(len(metrics))
        total_bars = len(groups) * 2
        offsets = np.linspace(-(total_bars - 1) * bar_width / 2,
                              (total_bars - 1) * bar_width / 2, total_bars)

        bar_idx = 0
        for model, hybrid, semantic in groups:
            h_vals = [hybrid[m] for m in metrics]
            s_vals = [semantic[m] for m in metrics]

            model_short = model.split('-')[0] if '-' in model else model[:6]
            ax.bar(x + offsets[bar_idx], h_vals, bar_width,
                   color=COLORS['hybrid'], edgecolor='black', linewidth=0.5,
                   label=f'Hybrid ({model_short})')
            bar_idx += 1
            ax.bar(x + offsets[bar_idx], s_vals, bar_width,
                   color=COLORS['semantic'], edgecolor='black', linewidth=0.5,
                   label=f'Semantic ({model_short})')
            bar_idx += 1

        ax.set_xticks(x)
        ax.set_xticklabels(metric_labels, rotation=15, ha='right')
        ax.set_title(ds, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        if ax_idx == 0:
            ax.set_ylabel('Score', fontweight='bold')
            ax.legend(loc='upper right', fontsize=7, frameon=True, edgecolor='black')

    plt.suptitle('Experiment 1: Hybrid RRF vs Pure Semantic Retrieval', fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'main_comparison.pdf', format='pdf')
    plt.savefig(FIGURES_DIR / 'main_comparison.png', format='png')
    print(f"Saved: {FIGURES_DIR / 'main_comparison.png'}")
    plt.close()


def plot_recall_heatmap(results):
    """Figure 2: Recall@10 heatmap — systems × (dataset, model) grid."""
    systems = sorted(set(r['system'] for r in results))
    conditions = []
    for r in results:
        cond = f"{r['dataset']}\n({r['model'][:6]})"
        if cond not in conditions:
            conditions.append(cond)

    matrix = np.zeros((len(systems), len(conditions)))
    for r in results:
        sys_idx = systems.index(r['system'])
        cond = f"{r['dataset']}\n({r['model'][:6]})"
        cond_idx = conditions.index(cond)
        matrix[sys_idx, cond_idx] = r['recall_10']

    fig, ax = plt.subplots(figsize=(max(4, len(conditions) * 1.8), 3))
    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto', vmin=0, vmax=max(0.5, matrix.max() * 1.2))

    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels(conditions, fontsize=8)
    ax.set_yticks(range(len(systems)))
    sys_labels = ['Hybrid RRF' if 'Hybrid' in s else 'Pure Semantic' for s in systems]
    ax.set_yticklabels(sys_labels, fontsize=9)

    for i in range(len(systems)):
        for j in range(len(conditions)):
            val = matrix[i, j]
            color = 'white' if val > matrix.max() * 0.6 else 'black'
            ax.text(j, i, f'{val:.3f}', ha='center', va='center', fontsize=9,
                    fontweight='bold', color=color)

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Recall@10', fontsize=9)
    ax.set_title('Recall@10 Across All Conditions', fontweight='bold')

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'recall_heatmap.pdf', format='pdf')
    plt.savefig(FIGURES_DIR / 'recall_heatmap.png', format='png')
    print(f"Saved: {FIGURES_DIR / 'recall_heatmap.png'}")
    plt.close()


def plot_category_breakdown(results):
    """Figure 3: Per-category Recall@10 for each dataset."""
    datasets = sorted(set(r['dataset'] for r in results))

    for ds in datasets:
        ds_results = [r for r in results if r['dataset'] == ds]
        if not ds_results or not ds_results[0].get('per_category'):
            continue

        all_cats = set()
        for r in ds_results:
            all_cats.update(r.get('per_category', {}).keys())
        categories = sorted(all_cats)

        if not categories:
            continue

        fig, ax = plt.subplots(figsize=(max(6, len(categories) * 1.2), 4.5))

        bar_width = 0.35 / max(1, len(ds_results) // 2)
        x = np.arange(len(categories))

        for i, r in enumerate(ds_results):
            color = COLORS['hybrid'] if 'Hybrid' in r['system'] else COLORS['semantic']
            model_short = r['model'][:6]
            label = f"{'Hybrid' if 'Hybrid' in r['system'] else 'Semantic'} ({model_short})"
            values = [r.get('per_category', {}).get(cat, {}).get('recall_10', 0) for cat in categories]
            offset = (i - len(ds_results) / 2 + 0.5) * bar_width
            ax.bar(x + offset, values, bar_width * 0.9, label=label, color=color,
                   alpha=0.7 + 0.3 * (i % 2), edgecolor='black', linewidth=0.5)

        ax.set_xticks(x)
        ax.set_xticklabels(categories, rotation=30, ha='right', fontsize=8)
        ax.set_ylabel('Recall@10', fontweight='bold')
        ax.set_title(f'{ds}: Recall@10 by Question Category', fontweight='bold')
        ax.legend(fontsize=7, loc='best', frameon=True, edgecolor='black')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)

        plt.tight_layout()
        safe_ds = ds.replace(' ', '_').replace('/', '_')
        plt.savefig(FIGURES_DIR / f'category_breakdown_{safe_ds}.pdf', format='pdf')
        plt.savefig(FIGURES_DIR / f'category_breakdown_{safe_ds}.png', format='png')
        print(f"Saved: {FIGURES_DIR / f'category_breakdown_{safe_ds}.png'}")
        plt.close()


def plot_hybrid_advantage(results):
    """Figure 4: Hybrid advantage (delta Recall) across conditions."""
    datasets = sorted(set(r['dataset'] for r in results))
    models = sorted(set(r['model'] for r in results))

    conditions = []
    deltas_r5 = []
    deltas_r10 = []
    deltas_mrr = []

    for ds in datasets:
        for model in models:
            hybrid = next((r for r in results if r['dataset'] == ds and r['model'] == model
                           and 'Hybrid' in r['system']), None)
            semantic = next((r for r in results if r['dataset'] == ds and r['model'] == model
                             and 'Semantic' in r['system']), None)
            if hybrid and semantic:
                label = f"{ds}\n({model[:6]})"
                conditions.append(label)
                deltas_r5.append(hybrid['recall_5'] - semantic['recall_5'])
                deltas_r10.append(hybrid['recall_10'] - semantic['recall_10'])
                deltas_mrr.append(hybrid['mrr_10'] - semantic['mrr_10'])

    if not conditions:
        return

    fig, ax = plt.subplots(figsize=(max(5, len(conditions) * 2), 4))
    x = np.arange(len(conditions))
    width = 0.25

    bars1 = ax.bar(x - width, deltas_r5, width, label='$\\Delta$ Recall@5',
                   color=COLORS['hybrid'], edgecolor='black', linewidth=0.5)
    bars2 = ax.bar(x, deltas_r10, width, label='$\\Delta$ Recall@10',
                   color=COLORS['minilm'], edgecolor='black', linewidth=0.5)
    bars3 = ax.bar(x + width, deltas_mrr, width, label='$\\Delta$ MRR@10',
                   color=COLORS['accent'], edgecolor='black', linewidth=0.5)

    ax.axhline(y=0, color='black', linewidth=0.8, linestyle='-')
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, fontsize=8)
    ax.set_ylabel('Hybrid - Semantic (delta)', fontweight='bold')
    ax.set_title('Hybrid Retrieval Advantage Over Pure Semantic', fontweight='bold')
    ax.legend(loc='best', fontsize=8, frameon=True, edgecolor='black')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)

    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            val = bar.get_height()
            color = '#006400' if val > 0 else '#8B0000'
            ax.text(bar.get_x() + bar.get_width() / 2, val,
                    f'{val:+.3f}', ha='center', va='bottom' if val >= 0 else 'top',
                    fontsize=7, fontweight='bold', color=color)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'hybrid_advantage.pdf', format='pdf')
    plt.savefig(FIGURES_DIR / 'hybrid_advantage.png', format='png')
    print(f"Saved: {FIGURES_DIR / 'hybrid_advantage.png'}")
    plt.close()


def plot_latency_comparison(results):
    """Figure 5: Latency comparison across all conditions."""
    conditions = []
    hybrid_latencies = []
    semantic_latencies = []

    datasets = sorted(set(r['dataset'] for r in results))
    models = sorted(set(r['model'] for r in results))

    for ds in datasets:
        for model in models:
            hybrid = next((r for r in results if r['dataset'] == ds and r['model'] == model
                           and 'Hybrid' in r['system']), None)
            semantic = next((r for r in results if r['dataset'] == ds and r['model'] == model
                             and 'Semantic' in r['system']), None)
            if hybrid and semantic:
                conditions.append(f"{ds}\n({model[:6]})")
                hybrid_latencies.append(hybrid['avg_latency_ms'])
                semantic_latencies.append(semantic['avg_latency_ms'])

    if not conditions:
        return

    fig, ax = plt.subplots(figsize=(max(5, len(conditions) * 2), 4))
    x = np.arange(len(conditions))
    width = 0.35

    ax.bar(x - width / 2, hybrid_latencies, width, label='Hybrid RRF',
           color=COLORS['hybrid'], edgecolor='black', linewidth=0.5)
    ax.bar(x + width / 2, semantic_latencies, width, label='Pure Semantic',
           color=COLORS['semantic'], edgecolor='black', linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels(conditions, fontsize=8)
    ax.set_ylabel('Avg Latency (ms)', fontweight='bold')
    ax.set_title('Retrieval Latency Comparison', fontweight='bold')
    ax.legend(loc='upper right', fontsize=8, frameon=True, edgecolor='black')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'latency_comparison.pdf', format='pdf')
    plt.savefig(FIGURES_DIR / 'latency_comparison.png', format='png')
    print(f"Saved: {FIGURES_DIR / 'latency_comparison.png'}")
    plt.close()


def plot_results_table(results):
    """Figure 6: Results table as a figure (for paper inclusion)."""
    fig, ax = plt.subplots(figsize=(12, max(3, 0.5 * len(results) + 1.5)))
    ax.axis('off')

    headers = ['System', 'Model', 'Dataset', 'Recall@5', 'Recall@10', 'MRR@10', 'Hit@10', 'Latency(ms)']
    cell_text = []
    for r in results:
        sys_short = 'Hybrid RRF' if 'Hybrid' in r['system'] else 'Pure Semantic'
        cell_text.append([
            sys_short, r['model'][:15], r['dataset'],
            f"{r['recall_5']:.4f}", f"{r['recall_10']:.4f}",
            f"{r['mrr_10']:.4f}", f"{r['hit_10']:.4f}",
            f"{r['avg_latency_ms']:.2f}"
        ])

    colors = []
    for r in results:
        if 'Hybrid' in r['system']:
            colors.append([COLORS['hybrid_light']] * len(headers))
        else:
            colors.append([COLORS['semantic_light']] * len(headers))

    table = ax.table(cellText=cell_text, colLabels=headers, loc='center',
                     cellColours=colors, cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(fontweight='bold')
            cell.set_facecolor('#2F4F4F')
            cell.set_text_props(color='white', fontweight='bold')
        cell.set_edgecolor('black')
        cell.set_linewidth(0.5)

    ax.set_title('Experiment 1: Full Results Matrix', fontweight='bold', pad=20, fontsize=13)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'results_table.pdf', format='pdf')
    plt.savefig(FIGURES_DIR / 'results_table.png', format='png')
    print(f"Saved: {FIGURES_DIR / 'results_table.png'}")
    plt.close()


def main():
    print("=" * 60)
    print("Experiment 1: Generating Visualizations")
    print("=" * 60)

    results = load_results()
    print(f"Loaded {len(results)} result entries")

    plot_main_comparison(results)
    plot_recall_heatmap(results)
    plot_category_breakdown(results)
    plot_hybrid_advantage(results)
    plot_latency_comparison(results)
    plot_results_table(results)

    print(f"\nAll figures saved to: {FIGURES_DIR}")
    print("Done!")


if __name__ == "__main__":
    main()
