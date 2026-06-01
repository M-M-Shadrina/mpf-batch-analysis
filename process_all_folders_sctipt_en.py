import os
import sys
import subprocess
import pandas as pd
import numpy as np
from pathlib import Path
import nibabel as nib
from datetime import datetime
import time
import gc


# Mapping of structure label numbers to names
STRUCTURE_NAMES = {
    2:  "Caudate_L",
    3:  "Caudate_R",
    4:  "Putamen_L",
    5:  "Putamen_R",
    6:  "Thalamus_L",
    7:  "Thalamus_R",
    8:  "Globus_pallidus_L",
    9:  "Globus_pallidus_R",
    10: "Hippocamp_L",
    11: "Hippocamp_R",
    12: "Amigdala_L",
    13: "Amigdala_R",
    14: "Corpus_callosum",
    15: "Fornix",
    16: "Brainstem",
    17: "Pons",
    18: "Substantia_nigra_L",
    19: "Substantia_nigra_R",
    20: "Occipital_cortex_L_GM",
    21: "Occipital_cortex_R_GM",
    22: "Parietal_cortex_L_GM",
    23: "Parietal_cortex_R_GM",
    24: "Insular_cortex_L_GM",
    25: "Insular_cortex_R_GM",
    26: "Temporal_cortex_L_GM",
    27: "Temporal_cortex_R_GM",
    28: "Frontal_cortex_L_GM",
    29: "Frontal_cortex_R_GM",
    30: "Label 30",
    32: "Cerebellum_L_GM",
    33: "Cerebellum_R_GM",
    40: "Occipital_cortex_L_WM",
    42: "Occipital_cortex_R_WM",
    44: "Parietal_cortex_L_WM",
    46: "Parietal_cortex_R_WM",
    48: "Insular_cortex_L_WM",
    50: "Insular_cortex_R_WM",
    52: "Temporal_cortex_L_WM",
    54: "Temporal_cortex_R_WM",
    56: "Frontal_cortex_L_WM",
    58: "Frontal_cortex_R_GM",
    60: "Label 60",
    64: "Cerebellum_L_WM",
    66: "Cerebellum_R_WM",
}

# Column order for output — service labels excluded
ORDERED_COLUMNS = [name for name in STRUCTURE_NAMES.values()
                   if not name.startswith("Label")]


def find_mri_file(folder_path):
    """Search for an MRI file in the given folder"""
    folder_path = Path(folder_path)

    possible_names = [
        "MPFuncor_coef_transform.nii",
        "MPFuncor_coef_transform.nii.gz",
        "MPFuncor_coef_transform",
        "MPFuncor_transform.nii.gz",
        "MPFuncor_transform.nii",
    ]

    for name in possible_names:
        test_path = folder_path / name
        if test_path.exists():
            return test_path
    return None


def run_segmentation_script(script_path, folder_path):
    """Run the processing script for a single folder"""
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), str(folder_path)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(folder_path)
        )

        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    print(f"    {line}")

        if result.returncode != 0:
            if result.stderr:
                print(f"    Error: {result.stderr[:300]}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print(f"    Timeout exceeded (5 minutes)")
        return False
    except Exception as e:
        print(f"    Failed to run script: {str(e)}")
        return False


def compute_metrics_per_structure(seg_path, mri_path):
    """
    Compute metrics for each structure in the segmentation file.
    Returns a list of dicts with metrics for each structure.
    """
    try:
        print(f"    Loading files...")
        seg_img = nib.load(str(seg_path))
        mri_img = nib.load(str(mri_path))

        seg_data = seg_img.get_fdata()
        mri_data = mri_img.get_fdata()

        print(f"    Segmentation shape: {seg_data.shape}")
        print(f"    MRI shape: {mri_data.shape}")

        if seg_data.shape != mri_data.shape:
            print(f"    Warning: shape mismatch, cropping to minimum size...")
            min_shape = tuple(min(s, m) for s, m in zip(seg_data.shape, mri_data.shape))
            seg_data = seg_data[:min_shape[0], :min_shape[1], :min_shape[2]]
            mri_data = mri_data[:min_shape[0], :min_shape[1], :min_shape[2]]

        zooms = seg_img.header.get_zooms()[:3]
        voxel_volume = np.prod(zooms)

        unique_values = np.unique(seg_data)
        unique_values = unique_values[unique_values > 0]
        unique_values = unique_values[~np.isnan(unique_values)]

        print(f"    Structures found: {len(unique_values)}")

        results = []

        for value in unique_values:
            mask = (seg_data == value)
            voxel_count = np.sum(mask)

            if voxel_count == 0:
                continue

            mean_intensity = np.mean(mri_data[mask])
            volume_mm3 = voxel_count * voxel_volume
            volume_ml = volume_mm3 / 1000

            results.append({
                'structure_number': int(value),
                'voxel_count': int(voxel_count),
                'mean_intensity': float(mean_intensity),
                'volume_mm3': float(volume_mm3),
                'volume_ml': float(volume_ml)
            })

            if len(results) % 10 == 0:
                print(f"      Processed structures: {len(results)}/{len(unique_values)}")

        del seg_data, mri_data
        gc.collect()

        print(f"    Successfully processed structures: {len(results)}")
        return results

    except Exception as e:
        print(f"    Computation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def save_results(all_results, folders, successful, failed, elapsed_time, output_path):
    """Save results to an Excel file with two sheets"""
    print(f"\n{'=' * 70}")
    print("SAVING RESULTS")
    print(f"{'=' * 70}")

    if not all_results:
        print("[ERROR] No data to save")
        return

    df = pd.DataFrame(all_results)
    df = df[['folder', 'structure_number', 'mean_intensity',
             'volume_ml', 'volume_mm3', 'voxel_count']]

    # Replace label numbers with structure names (unknown labels kept as strings)
    df['structure_name'] = df['structure_number'].map(STRUCTURE_NAMES).fillna(
        df['structure_number'].astype(str)
    )

    # Duplicate diagnostics
    dupes = df[df.duplicated(subset=['folder', 'structure_name'], keep=False)]
    if not dupes.empty:
        print(f"  Warning: duplicate structures found (mean will be used):")
        print(dupes[['folder', 'structure_name', 'structure_number']].to_string())

    # Build pivot tables: rows = folders, columns = structures
    pivot_intensity = df.pivot_table(
        index='folder',
        columns='structure_name',
        values='mean_intensity',
        aggfunc='mean'
    )
    pivot_volume = df.pivot_table(
        index='folder',
        columns='structure_name',
        values='volume_ml',
        aggfunc='mean'
    )

    # Apply column order and drop service labels
    intensity_cols = [c for c in ORDERED_COLUMNS if c in pivot_intensity.columns]
    volume_cols = [c for c in ORDERED_COLUMNS if c in pivot_volume.columns]

    pivot_intensity = pivot_intensity[intensity_cols]
    pivot_volume = pivot_volume[volume_cols]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        result_file = output_path / f"results_{timestamp}.xlsx"
        with pd.ExcelWriter(result_file, engine='openpyxl') as writer:
            pivot_intensity.to_excel(writer, sheet_name='Mean_Intensity')
            pivot_volume.to_excel(writer, sheet_name='Volume_mL')

        print(f"[OK] File saved: {result_file}")
        print(f"     Sheet 'Mean_Intensity' — mean intensity values")
        print(f"     Sheet 'Volume_mL'      — volumes in mL")

    except Exception as e:
        print(f"[ERROR] Could not save Excel file: {e}")
        csv_i = output_path / f"mean_intensity_{timestamp}.csv"
        csv_v = output_path / f"volume_{timestamp}.csv"
        pivot_intensity.to_csv(csv_i, encoding='utf-8-sig')
        pivot_volume.to_csv(csv_v, encoding='utf-8-sig')
        print(f"[OK] Saved as CSV: {csv_i.name}, {csv_v.name}")

    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"Total folders:          {len(folders)}")
    print(f"Successfully processed: {successful}")
    print(f"Failed:                 {failed}")
    print(f"Unique structures:      {df['structure_number'].nunique()}")
    print(f"Processing time:        {elapsed_time / 60:.1f} minutes")


def process_all_folders(base_path, script_path, output_path):
    """Process all subfolders in base_path"""
    base_path = Path(base_path)
    script_path = Path(script_path)
    output_path = Path(output_path)

    if not base_path.exists():
        print(f"ERROR: Folder does not exist - {base_path}")
        return

    if not script_path.exists():
        print(f"ERROR: Script not found - {script_path}")
        return

    folders = [f for f in base_path.iterdir() if f.is_dir()]

    if not folders:
        print("No folders to process")
        return

    print("=" * 70)
    print("MRI SEGMENTATION PROCESSING")
    print("=" * 70)
    print(f"Data path:        {base_path}")
    print(f"Processing script:{script_path}")
    print(f"Output folder:    {output_path}")
    print(f"Folders found:    {len(folders)}")
    print("=" * 70)

    confirm = input(f"\nWARNING: {len(folders)} folders will be processed. Continue? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("Cancelled")
        return

    all_results = []
    successful = 0
    failed = 0
    start_time = time.time()

    for i, folder in enumerate(folders, 1):
        print(f"\n{'=' * 70}")
        print(f"[{i}/{len(folders)}] Processing: {folder.name}")
        print(f"{'=' * 70}")

        try:
            print("  Step 1: Running segmentation script...")
            script_success = run_segmentation_script(script_path, folder)

            if not script_success:
                print(f"  [ERROR] Script finished with error")
                failed += 1
                continue

            print(f"  [OK] Script completed successfully")

            final_seg = folder / "combined_result.nii.gz"
            if not final_seg.exists():
                print(f"  [ERROR] combined_result.nii.gz was not created")
                failed += 1
                continue

            print(f"  [OK] Segmentation file created")

            mri_file = find_mri_file(folder)
            if not mri_file:
                print(f"  [ERROR] MRI file not found")
                failed += 1
                continue

            print(f"  [OK] MRI file found: {mri_file.name}")

            print("  Step 2: Computing metrics per structure...")
            structures_metrics = compute_metrics_per_structure(final_seg, mri_file)

            if structures_metrics:
                for metrics in structures_metrics:
                    metrics['folder'] = folder.name
                    all_results.append(metrics)

                successful += 1
                print(f"  [OK] Structures processed: {len(structures_metrics)}")
                print(f"  Sample structures:")
                for m in structures_metrics[:5]:
                    print(f"    Structure {m['structure_number']}: "
                          f"intensity={m['mean_intensity']:.2f}, "
                          f"volume={m['volume_ml']:.2f} mL")
            else:
                print(f"  [ERROR] Could not compute metrics")
                failed += 1

        except Exception as e:
            print(f"  [ERROR] Critical error: {str(e)}")
            failed += 1
            continue

        gc.collect()
        time.sleep(0.5)

    elapsed_time = time.time() - start_time
    save_results(all_results, folders, successful, failed, elapsed_time, output_path)

    print(f"\n{'=' * 70}")
    print("PROCESSING COMPLETE")
    print(f"{'=' * 70}")


def test_single_folder(base_path, script_path):
    """Run a test on a single folder"""
    base_path = Path(base_path)

    folders = [f for f in base_path.iterdir() if f.is_dir()]

    if not folders:
        print("No folders available for testing")
        return

    print("\nAvailable folders:")
    for i, f in enumerate(folders[:10], 1):
        print(f"  {i}. {f.name}")

    try:
        choice = int(input("\nSelect folder number for test: ")) - 1
        folder = folders[choice] if 0 <= choice < len(folders) else folders[0]
    except Exception:
        print("Invalid input, using first folder")
        folder = folders[0]

    print(f"\n{'=' * 70}")
    print(f"TEST ON FOLDER: {folder.name}")
    print(f"{'=' * 70}")

    print("\n1. Running processing script...")
    success = run_segmentation_script(script_path, folder)

    if success:
        print("[OK] Script completed successfully")

        print("\n2. Checking created files:")
        expected_files = [
            "remapped.nii.gz",
            "remapped_GM.nii.gz",
            "remapped_WM.nii.gz",
            "MPFuncor_coef_transform_WM_GM.nii",
            "multiplied_result.nii",
            "combined_result.nii.gz"
        ]

        for filename in expected_files:
            file_path = folder / filename
            if file_path.exists():
                size = file_path.stat().st_size / 1024 / 1024
                print(f"  [OK] {filename} ({size:.1f} MB)")
            else:
                print(f"  [MISSING] {filename}")

        final_seg = folder / "combined_result.nii.gz"
        mri_file = find_mri_file(folder)

        if final_seg.exists() and mri_file:
            print("\n3. Computing structure metrics...")
            metrics = compute_metrics_per_structure(final_seg, mri_file)
            if metrics:
                print(f"  [OK] Structures found: {len(metrics)}")
                print(f"  First 5 structures:")
                for m in metrics[:5]:
                    print(f"    Structure {m['structure_number']}: "
                          f"intensity={m['mean_intensity']:.2f}, "
                          f"volume={m['volume_ml']:.2f} mL")
            else:
                print("  [ERROR] Could not compute metrics")
    else:
        print("[ERROR] Script did not complete successfully")


if __name__ == "__main__":
    # ========== INPUT PATHS ==========
    base_path = input("Enter path to data folder: ").strip().strip('"')
    if not os.path.isdir(base_path):
        print(f"Error: folder '{base_path}' not found.")
        sys.exit(1)

    script_path = input("Enter path to processing script: ").strip().strip('"')
    if not os.path.isfile(script_path):
        print(f"Error: script '{script_path}' not found.")
        sys.exit(1)

    output_path = input("Enter path to save results (Enter — save next to data): ").strip().strip('"')
    if output_path == "":
        output_path = base_path
    elif not os.path.isdir(output_path):
        os.makedirs(output_path)
        print(f"Created folder: {output_path}")
    # =================================

    print("=" * 70)
    print("MRI SEGMENTATION AUTOMATION")
    print("=" * 70)
    print(f"Data folder:      {base_path}")
    print(f"Processing script:{script_path}")
    print(f"Output folder:    {output_path}")

    print("\nSELECT MODE:")
    print("1 - Test on a single folder")
    print("2 - Process all folders")

    mode = input("Your choice (1 or 2): ").strip()

    if mode == "1":
        test_single_folder(base_path, script_path)
    elif mode == "2":
        process_all_folders(base_path, script_path, output_path)
    else:
        print("Invalid choice")

    input("\nPress Enter to exit...")
