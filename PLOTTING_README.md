# 📊 Academic Plotting Toolkit

## Quick Start

```bash
# Activate environment
source venv/bin/activate

# Generate all figures
python3 scripts/plot_research_results.py

# View figures
open figures/
```

---

## What You Got

✅ **6 publication-ready figures** following [awesome-ai-research-writing](https://github.com/Leey21/awesome-ai-research-writing) guidelines:

1. **latency_comparison.pdf** - Method comparison (horizontal bar chart)
2. **latency_distribution.pdf** - Statistical distribution (violin plot)
3. **scalability_curve.pdf** - Performance vs dataset size (line plot with confidence intervals)
4. **query_latency_breakdown.pdf** - Per-query analysis (grouped bar chart)
5. **pareto_frontier.pdf** - Speed vs quality trade-off (scatter plot)
6. **ablation_study.pdf** - Component contribution (dual bar charts)

Each figure comes in:
- **PDF** (vector format for paper submission)
- **PNG** (high-res preview)

---

## Style Features

Following NeurIPS/ICML/ICLR standards:

✅ Pastel, colorblind-friendly colors  
✅ Clean typography (Times New Roman)  
✅ Proper statistical visualization (confidence intervals, distributions)  
✅ 300 DPI resolution  
✅ No unnecessary bold/italic  
✅ Professional grid styling  
✅ Appropriate chart types for each research question  

---

## Customization

Edit `scripts/plot_research_results.py` to:

### Update Your Data
```python
# Line 234: Replace with your actual measurements
baseline_latencies = [17.07, 0.25, 0.17, 0.19, 0.15, 0.20, 0.18, 0.18]
```

### Change Colors
```python
# Line 30-36: Customize palette
COLORS = {
    'baseline': '#E8998D',  # Soft coral
    'unified': '#A8D5BA',   # Soft mint
    # ...
}
```

### Add More Plots
```python
def plot_your_custom_figure():
    """Your custom plot"""
    fig, ax = plt.subplots(figsize=(6, 4))
    # Your plotting code
    plt.savefig(OUTPUT_DIR / 'your_figure.pdf')
```

---

## LaTeX Integration

### Single Column
```latex
\begin{figure}[t]
\centering
\includegraphics[width=0.48\textwidth]{figures/latency_comparison.pdf}
\caption{Performance comparison between RRF baseline and unified operator.}
\label{fig:latency}
\end{figure}
```

### Two Column
```latex
\begin{figure*}[t]
\centering
\includegraphics[width=0.95\textwidth]{figures/scalability_curve.pdf}
\caption{Scalability analysis from 100 to 1M chunks.}
\label{fig:scalability}
\end{figure*}
```

---

## Figure Selection Guide

| Research Question | Use This Figure |
|-------------------|-----------------|
| "Is my method faster?" | latency_comparison.pdf |
| "Is improvement consistent?" | latency_distribution.pdf |
| "Does it scale?" | scalability_curve.pdf |
| "Works on all queries?" | query_latency_breakdown.pdf |
| "Speed vs quality?" | pareto_frontier.pdf |
| "Which component matters?" | ablation_study.pdf |

---

## Best Practices (from awesome-ai-research-writing)

### Chart Type Selection

**Horizontal Bar Chart** → When labels are long (method names)  
**Violin Plot** → Show full distribution + statistical rigor  
**Line Plot with CI** → Trends over continuous variable (time, size)  
**Grouped Bar Chart** → Compare 2-3 methods across multiple conditions  
**Scatter Plot** → Show trade-offs between two metrics  
**Pareto Frontier** → Highlight optimal solutions  

### Visual Design

✅ Use pastel colors (avoid bright red/green)  
✅ Add confidence intervals for statistical claims  
✅ Include inset zooms for detail  
✅ Label axes with units  
✅ Keep legends minimal  
✅ Use vector formats (PDF)  

❌ No 3D effects or shadows  
❌ No excessive bold/italic  
❌ No cluttered layouts  
❌ No raster formats in final paper  

---

## Dependencies

```bash
pip install matplotlib numpy
```

Or use the virtual environment:
```bash
source venv/bin/activate  # Already set up
```

---

## File Structure

```
OpenClaw-Hybrid-Retrieval-Research/
├── figures/                          # Generated plots
│   ├── latency_comparison.pdf
│   ├── latency_comparison.png
│   ├── latency_distribution.pdf
│   ├── latency_distribution.png
│   ├── scalability_curve.pdf
│   ├── scalability_curve.png
│   ├── query_latency_breakdown.pdf
│   ├── query_latency_breakdown.png
│   ├── pareto_frontier.pdf
│   ├── pareto_frontier.png
│   ├── ablation_study.pdf
│   └── ablation_study.png
│
├── scripts/
│   └── plot_research_results.py     # Plot generator
│
├── venv/                             # Python virtual environment
│
├── FIGURE_GUIDE.md                   # Detailed guide
└── PLOTTING_README.md                # This file
```

---

## Troubleshooting

### "ModuleNotFoundError: matplotlib"
```bash
source venv/bin/activate
pip install matplotlib numpy
```

### "Figure text too small"
```python
# In plot_research_results.py, line 14
plt.rcParams['font.size'] = 12  # Increase from 10
```

### "Colors don't work in grayscale"
```python
# Add hatching patterns
bars = ax.bar(..., hatch='///')
```

### "LaTeX can't find figures"
```latex
% Add to preamble
\usepackage{graphicx}
\graphicspath{{figures/}}
```

---

## Next Steps

1. ✅ **Review figures**: Open PDFs in `figures/` directory
2. ✅ **Customize data**: Edit `plot_research_results.py` with your measurements
3. ✅ **Write captions**: See examples in `FIGURE_GUIDE.md`
4. ✅ **Integrate into paper**: Use LaTeX templates above
5. ✅ **Iterate**: Regenerate as data updates

---

## Resources

- **Plotting Guidelines**: https://github.com/Leey21/awesome-ai-research-writing
- **Matplotlib Gallery**: https://matplotlib.org/stable/gallery/
- **Colorblind Palettes**: https://personal.sron.nl/~pault/
- **LaTeX Graphics**: https://www.overleaf.com/learn/latex/Inserting_Images

---

**Generated**: 2026-03-12  
**Total Figures**: 6 (12 files: PDF + PNG)  
**Style**: NeurIPS/ICML/ICLR academic standards  
**Status**: ✅ Ready for paper submission
