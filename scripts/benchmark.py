#!/usr/bin/env python
"""
Performance Benchmark: fastgeotoolkit vs GeoPandas
Compares GPX parsing and density computation for the Swiss trail dataset.
"""

import sys
import os
import glob
import time
import psutil
import gc
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import unary_union
import matplotlib.pyplot as plt
import numpy as np
import requests
import subprocess

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))

# ============================================================
# 1. BENCHMARK: GPX PARSING (fastgeotoolkit vs GeoPandas)
# ============================================================

def benchmark_gpx_parsing(gpx_files, num_iterations=3):
    """
    Compare GPX parsing performance:
    - fastgeotoolkit: via Node.js HTTP server
    - GeoPandas: native GPX reading with fiona
    """
    results = {
        'fastgeotoolkit': {'times': [], 'memory': []},
        'geopandas': {'times': [], 'memory': []}
    }

    # --- Benchmark fastgeotoolkit ---
    print("\n🔬 Benchmarking fastgeotoolkit GPX parsing...")
    for i in range(num_iterations):
        gc.collect()
        process = psutil.Process()
        mem_start = process.memory_info().rss / 1024 / 1024  # MB

        try:
            start = time.time()
            response = requests.post(
                'http://localhost:3000/process',
                json={'files': gpx_files},
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            elapsed = time.time() - start
            mem_end = process.memory_info().rss / 1024 / 1024
            results['fastgeotoolkit']['times'].append(elapsed)
            results['fastgeotoolkit']['memory'].append(mem_end - mem_start)
            print(f"  Iteration {i+1}: {elapsed:.2f}s, Memory Δ: {mem_end - mem_start:.1f} MB")
        except Exception as e:
            print(f"  Error: {e}")

    # --- Benchmark GeoPandas ---
    print("\n🔬 Benchmarking GeoPandas GPX parsing...")
    for i in range(num_iterations):
        gc.collect()
        process = psutil.Process()
        mem_start = process.memory_info().rss / 1024 / 1024  # MB

        try:
            start = time.time()
            all_tracks = []
            skipped = 0
            for gpx in gpx_files:
                try:
                    gdf = gpd.read_file(gpx, layer='tracks')
                    if not gdf.empty:
                        all_tracks.append(gdf)
                except Exception as e:
                    if "IllegalArgumentException" in str(e) or "point array" in str(e):
                        skipped += 1
                    else:
                        pass  # ignore other errors for speed
            if all_tracks:
                combined = pd.concat(all_tracks, ignore_index=True)
                trails = gpd.GeoDataFrame(combined, crs="EPSG:4326")
            elapsed = time.time() - start
            mem_end = process.memory_info().rss / 1024 / 1024
            results['geopandas']['times'].append(elapsed)
            results['geopandas']['memory'].append(mem_end - mem_start)
            print(f"  Iteration {i+1}: {elapsed:.2f}s, Memory Δ: {mem_end - mem_start:.1f} MB (skipped {skipped} invalid)")
        except Exception as e:
            print(f"  Error: {e}")

    return results


# ============================================================
# 2. BENCHMARK: DENSITY COMPUTATION
# ============================================================

def benchmark_density_computation(gpx_files, protected_gdf, num_iterations=3):
    """
    Compare route density computation:
    - fastgeotoolkit: native density mapping with frequency output
    - GeoPandas: buffer + union (simulated density)
    """
    results = {
        'fastgeotoolkit': {'times': [], 'memory': []},
        'geopandas': {'times': [], 'memory': []}
    }

    # --- Benchmark fastgeotoolkit (density via server) ---
    print("\n🔬 Benchmarking fastgeotoolkit density computation...")
    for i in range(num_iterations):
        gc.collect()
        process = psutil.Process()
        mem_start = process.memory_info().rss / 1024 / 1024

        try:
            start = time.time()
            response = requests.post(
                'http://localhost:3000/process',
                json={'files': gpx_files},
                timeout=300
            )
            response.raise_for_status()
            data = response.json()
            density_result = data['tracks']
            elapsed = time.time() - start
            mem_end = process.memory_info().rss / 1024 / 1024
            results['fastgeotoolkit']['times'].append(elapsed)
            results['fastgeotoolkit']['memory'].append(mem_end - mem_start)
            print(f"  Iteration {i+1}: {elapsed:.2f}s, Memory Δ: {mem_end - mem_start:.1f} MB")
        except Exception as e:
            print(f"  Error: {e}")

    # --- Benchmark GeoPandas (simulate density via buffering) ---
    print("\n🔬 Benchmarking GeoPandas density computation...")
    trails_gdf = None

    # Load trails with GeoPandas, skipping invalid files
    print("  Loading trails with GeoPandas (one-time cost)...")
    all_tracks = []
    skipped = 0
    for gpx in gpx_files:
        try:
            gdf = gpd.read_file(gpx, layer='tracks')
            if not gdf.empty:
                all_tracks.append(gdf)
        except Exception as e:
            if "IllegalArgumentException" in str(e) or "point array" in str(e):
                skipped += 1
            else:
                print(f"  Warning: Could not read {gpx}: {e}")
    
    if skipped > 0:
        print(f"  Skipped {skipped} files with invalid geometries")
    
    if all_tracks:
        combined = pd.concat(all_tracks, ignore_index=True)
        trails_gdf = gpd.GeoDataFrame(combined, crs="EPSG:4326")
        trails_gdf = trails_gdf.to_crs('EPSG:2056')
        print(f"  Loaded {len(trails_gdf)} valid tracks")
    else:
        print("  No valid tracks loaded for GeoPandas benchmark.")
        return results

    if trails_gdf is not None and not trails_gdf.empty:
        for i in range(num_iterations):
            gc.collect()
            process = psutil.Process()
            mem_start = process.memory_info().rss / 1024 / 1024

            try:
                start = time.time()
                buffered = trails_gdf.geometry.buffer(10)
                union = unary_union(buffered)
                density_area = union.area
                elapsed = time.time() - start
                mem_end = process.memory_info().rss / 1024 / 1024
                results['geopandas']['times'].append(elapsed)
                results['geopandas']['memory'].append(mem_end - mem_start)
                print(f"  Iteration {i+1}: {elapsed:.2f}s, Memory Δ: {mem_end - mem_start:.1f} MB")
            except Exception as e:
                print(f"  Error: {e}")

    return results


# ============================================================
# 3. GENERATE REPORT AND TABLE
# ============================================================

def generate_report(gpx_parsing, density_computation, output_file='benchmark_results.json'):
    report = {
        'gpx_parsing': {},
        'density_computation': {},
        'summary': {}
    }

    for method in ['fastgeotoolkit', 'geopandas']:
        for task, data in [('gpx_parsing', gpx_parsing), ('density_computation', density_computation)]:
            times = data[method]['times']
            mem = data[method]['memory']
            if times:
                report[task][method] = {
                    'mean_time_s': round(sum(times) / len(times), 2),
                    'std_time_s': round(np.std(times), 2),
                    'mean_memory_mb': round(sum(mem) / len(mem), 1) if mem else None,
                    'times': times,
                    'memory': mem
                }
            else:
                report[task][method] = {'mean_time_s': None, 'std_time_s': None, 'mean_memory_mb': None}

    # Speedups
    if (report['gpx_parsing']['fastgeotoolkit']['mean_time_s'] and
        report['gpx_parsing']['geopandas']['mean_time_s']):
        report['summary']['gpx_parsing_speedup'] = (
            report['gpx_parsing']['geopandas']['mean_time_s'] /
            report['gpx_parsing']['fastgeotoolkit']['mean_time_s']
        )

    if (report['density_computation']['fastgeotoolkit']['mean_time_s'] and
        report['density_computation']['geopandas']['mean_time_s']):
        report['summary']['density_speedup'] = (
            report['density_computation']['geopandas']['mean_time_s'] /
            report['density_computation']['fastgeotoolkit']['mean_time_s']
        )

    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    return report


def print_summary(report):
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)

    print("\n📊 GPX PARSING")
    print("-"*40)
    for method in ['fastgeotoolkit', 'geopandas']:
        data = report['gpx_parsing'][method]
        if data['mean_time_s']:
            print(f"  {method:15s}: {data['mean_time_s']:.2f}s ± {data['std_time_s']:.2f}s, "
                  f"Memory Δ: {data['mean_memory_mb']:.1f} MB")
    if 'gpx_parsing_speedup' in report['summary']:
        print(f"  ⚡ Speedup: {report['summary']['gpx_parsing_speedup']:.1f}x")

    print("\n📊 DENSITY COMPUTATION")
    print("-"*40)
    for method in ['fastgeotoolkit', 'geopandas']:
        data = report['density_computation'][method]
        if data['mean_time_s']:
            print(f"  {method:15s}: {data['mean_time_s']:.2f}s ± {data['std_time_s']:.2f}s, "
                  f"Memory Δ: {data['mean_memory_mb']:.1f} MB")
    if 'density_speedup' in report['summary']:
        print(f"  ⚡ Speedup: {report['summary']['density_speedup']:.1f}x")


def generate_latex_table(report):
    latex = r"""
\begin{table}[H]
\centering
\caption{Performance comparison: fastgeotoolkit vs GeoPandas}
\label{tab:benchmark}
\begin{tabular}{lrrr}
\toprule
\textbf{Task} & \textbf{fastgeotoolkit} & \textbf{GeoPandas} & \textbf{Speedup} \\
\midrule
"""
    if report['gpx_parsing']['fastgeotoolkit']['mean_time_s']:
        fg_time = report['gpx_parsing']['fastgeotoolkit']['mean_time_s']
        gp_time = report['gpx_parsing']['geopandas']['mean_time_s']
        speedup = gp_time / fg_time if fg_time > 0 else 0
        latex += f"GPX Parsing & {fg_time:.1f}s & {gp_time:.1f}s & {speedup:.1f}x \\\\\n"

    if report['density_computation']['fastgeotoolkit']['mean_time_s']:
        fg_time = report['density_computation']['fastgeotoolkit']['mean_time_s']
        gp_time = report['density_computation']['geopandas']['mean_time_s']
        speedup = gp_time / fg_time if fg_time > 0 else 0
        latex += f"Route Density & {fg_time:.1f}s & {gp_time:.1f}s & {speedup:.1f}x \\\\\n"

    if report['gpx_parsing']['fastgeotoolkit']['mean_memory_mb']:
        fg_mem = report['gpx_parsing']['fastgeotoolkit']['mean_memory_mb']
        gp_mem = report['gpx_parsing']['geopandas']['mean_memory_mb']
        mem_ratio = fg_mem / gp_mem if gp_mem > 0 else 0
        latex += f"Memory Usage (GPX) & {fg_mem:.1f} MB & {gp_mem:.1f} MB & {mem_ratio:.1f}x \\\\\n"

    latex += r"""
\bottomrule
\end{tabular}
\end{table}
"""
    return latex


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("="*60)
    print("fastgeotoolkit PERFORMANCE BENCHMARK")
    print("="*60)

    gpx_files = glob.glob('data/raw/*.gpx')
    if not gpx_files:
        print("\n❌ No GPX files found in data/raw/")
        sys.exit(1)

    print(f"\n📁 Found {len(gpx_files)} GPX files")

        # --- Check if fastgeotoolkit server is running ---
    def check_server(port=3000, timeout=10, retries=3):
        """Check if the fastgeotoolkit server is running and ready."""
        import time
        for attempt in range(retries):
            try:
                response = requests.get(f'http://localhost:{port}', timeout=timeout)
                if response.status_code == 200 or response.status_code == 404:  # server responds
                    print(f"✅ Server ready on port {port}")
                    return True
            except requests.exceptions.ConnectionError:
                print(f"  Attempt {attempt+1}/{retries}: Connection refused, retrying...")
                time.sleep(2)
            except requests.exceptions.Timeout:
                print(f"  Attempt {attempt+1}/{retries}: Timeout, retrying...")
                time.sleep(2)
            except Exception as e:
                print(f"  Attempt {attempt+1}/{retries}: {e}, retrying...")
                time.sleep(2)
        return False

    # In main:
    if not check_server():
        print("\n⚠️ fastgeotoolkit server not responding!")
        print("   Please start the server in another terminal:")
        print("   node src/javascript/server.mjs")
        print("   Make sure it says 'FastGeoToolkit server running on http://localhost:3000'")
        sys.exit(1)

    try:
        protected = gpd.read_file('data/boundaries/swiss_protected_areas_prepared.shp')
        print(f"   Protected area loaded: {len(protected)} features")
    except:
        protected = None
        print("   Protected area not found - density benchmark may be limited")

    print("\n🚀 Running benchmarks...")
    gpx_results = benchmark_gpx_parsing(gpx_files, num_iterations=3)
    density_results = benchmark_density_computation(gpx_files, protected, num_iterations=3)

    report = generate_report(gpx_results, density_results)
    print_summary(report)

    latex_table = generate_latex_table(report)
    os.makedirs('outputs', exist_ok=True)
    with open('outputs/benchmark_table.tex', 'w') as f:
        f.write(latex_table)
    print(f"\n✅ LaTeX table saved to outputs/benchmark_table.tex")

    with open('outputs/benchmark_results.json', 'w') as f:
        json.dump(report, f, indent=2)
    print(f"✅ Full results saved to outputs/benchmark_results.json")

    print("\n🎉 Benchmark complete!")