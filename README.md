# Trail Fragmentation in Swiss Protected Areas

[![DOI](https://zenodo.org/badge/1280525611.svg)](https://doi.org/10.5281/zenodo.20869713)  
[![EarthArXiv](https://img.shields.io/badge/EarthArXiv-preprint-blue)](https://eartharxiv.org/...)  

This repository provides the complete code, data processing pipelines, and supplementary materials for the manuscript:

**Weimer, A. (2026).** *Quantifying Trail‑Induced Fragmentation in Swiss Protected Areas Using Large‑Scale GPS Trajectory Analysis.*  
EarthArXiv preprint. DOI: [10.31223/...] (replace with actual DOI)

The study uses a high‑performance computational pipeline based on [`fastgeotoolkit`](https://github.com/a0ax/fastgeotoolkit) to process thousands of GPS hiking tracks and all Swiss protected area polygons, producing fragmentation indices, trail densities, and core habitat estimates. The analysis includes buffer sensitivity tests (5–50 m) and validation against the official Swiss trail network.

## Repository Contents

- `src/` – Python scripts for preprocessing, fragmentation calculations, sensitivity analysis, validation, and mapping.
- `outputs/` – Generated figures, tables, and summary statistics (CSV).
- `requirements.txt` – Python dependencies.
- `LICENSE` – MIT License.

## Getting Started

### Prerequisites

- Python 3.13 or higher
- Node.js 22 or higher (for the `fastgeotoolkit` WebAssembly server)
- npm (to install the `fastgeotoolkit` package)

### Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/a0ax/TrailFragmentation.git
cd TrailFragmentation
pip install -r requirements.txt
npm install -g fastgeotoolkit
```

### Data Acquisition

The analysis requires three datasets:

1. **Swiss protected areas** – available from the Swiss Federal Office for the Environment (FOEN) via [opendata.swiss](https://opendata.swiss). Place the shapefile in `data/protected_areas/`.

2. **GPS hiking tracks** – from the hikr.org community (Kaggle dataset: *gpx‑tracks‑from‑hikr.org*). Place the CSV file in `data/gpx/`.

3. **Official Swiss trail network** (optional, for validation) – available from [SwissMobility](https://schweizmobil.ch). Place the GeoPackage in `data/official_trails/`.

> The raw GPS data are not redistributed in this repository due to licensing restrictions.

### Running the Pipeline

Start the `fastgeotoolkit` server in a separate terminal:

```bash
fastgeotoolkit-server
```

Then execute the main analysis:

```bash
python src/main.py --buffer 10 --grid-size 5
```

To run the buffer sensitivity analysis (5, 10, 25, 50 m):

```bash
python src/sensitivity.py
```

To validate against official trails:

```bash
python src/validate.py --official data/official_trails/swissmobility.gpkg
```

All outputs (maps, tables, and summary CSVs) are written to the `outputs/` directory.

## Citation

If you use this code or its outputs in your work, please cite both the manuscript and the software archive:

**Manuscript:**

```bibtex
@article{weimer2026trail,
  title={Quantifying Trail-Induced Fragmentation in Swiss Protected Areas Using Large-Scale GPS Trajectory Analysis},
  author={Weimer, Alexander},
  journal={EarthArXiv},
  year={2026},
  doi={10.31223/...}  % replace with actual EarthArXiv DOI
}
```

**Software and data archive (Zenodo):**

```bibtex
@software{weimer2026trail_code,
  author = {Weimer, Alexander},
  title = {Trail Fragmentation in Swiss Protected Areas – Code and Data},
  year = {2026},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.20869713}
}
```

## License

This project is distributed under the MIT License. See the `LICENSE` file for details.

## Acknowledgments

- Swiss Federal Office for the Environment (FOEN) for protected area data.
- hikr.org community for providing GPS tracks.
- SwissMobility for the official trail network.