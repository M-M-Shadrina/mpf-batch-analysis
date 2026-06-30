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

def find_mri_file(folder_path):
    """Search for the MRI file in a folder"""
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
        print(f"    Launch error: {str(e)}")
        return False


def compute_metrics_per_structure(seg_path, mri_path):
    """
    Compute metrics for each structure in the segmentation.
    Returns a list of dictionaries with metrics for each structure.
    """
    try:
        print(f"    Loading files...")
        # Load the files
        seg_img = nib.load(str(seg_path))
        mri_img = nib.load(str(mri_path))

        seg_data = seg_img.get_fdata()
        mri_data = mri_img.get_fdata()

        print(f"    Segmentation shape: {seg_data.shape}")
        print(f"    MRI shape: {mri_data.shape}")

        # Match dimensions if needed
        if seg_data.shape != mri_data.shape:
            print(f"    Warning: shapes do not match, cropping...")
            min_shape = tuple(min(s, m) for s, m in zip(seg_data.shape, mri_data.shape))
            seg_data = seg_data[:min_shape[0], :min_shape[1], :min_shape[2]]
            mri_data = mri_data[:min_shape[0], :min_shape[1], :min_shape[2]]

        # Get voxel volume (in mm^3)
        zooms = seg_img.header.get_zooms()[:3]
        voxel_volume = np.prod(zooms)

        # Find all unique values in the segmentation (excluding 0 - background)
        unique_values = np.unique(seg_data)
        unique_values = unique_values[unique_values > 0]  # remove background
        unique_values = unique_values[~np.isnan(unique_values)]  # remove NaN

        print(f"    Structures found: {len(unique_values)}")

        results = []

        # Compute metrics for each structure
        for value in unique_values:
            # Create a mask for the current structure
            mask = (seg_data == value)
            voxel_count = np.sum(mask)

            if voxel_count == 0:
                continue

            # Mean intensity within this structure
            mean_intensity = np.mean(mri_data[mask])

            # Structure volume
            volume_mm3 = voxel_count * voxel_volume
            volume_ml = volume_mm3 / 1000

            results.append({
                'structure_number': int(value),
                'voxel_count': int(voxel_count),
                'mean_intensity': float(mean_intensity),
                'volume_mm3': float(volume_mm3),
                'volume_ml': float(volume_ml)
            })

            if len(results) % 10 == 0:  # Print progress every 10 structures
                print(f"      Structures processed: {len(results)}/{len(unique_values)}")

        # Free memory
        del seg_data, mri_data
        gc.collect()

        print(f"    Structures successfully processed: {len(results)}")
        return results

    except Exception as e:
        print(f"    Computation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def process_all_folders(base_path, script_path):
    """Process all folders"""

    base_path = Path(base_path)
    script_path = Path(script_path)

    if not base_path.exists():
        print(f"ERROR: Folder does not exist - {base_path}")
        return

    if not script_path.exists():
        print(f"ERROR: Script not found - {script_path}")
        return

    # Get all subfolders
    folders = [f for f in base_path.iterdir() if f.is_dir()]

    if not folders:
        print("No folders to process")
        return

    print("="*70)
    print("SEGMENTATION PROCESSING AUTOMATION")
    print("="*70)
    print(f"Data path: {base_path}")
    print(f"Processing script: {script_path}")
    print(f"Folders found: {len(folders)}")
    print("="*70)

    print("\nWARNING: {} folders will be processed".format(len(folders)))
    confirm = input("Continue? (yes/no): ").strip().lower()

    if confirm not in ['yes', 'y']:
        print("Cancelled")
        return

    all_results = []  # List for all results
    successful = 0
    failed = 0

    start_time = time.time()

    for i, folder in enumerate(folders, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(folders)}] Processing: {folder.name}")
        print(f"{'='*70}")

        try:
            # 1. Run the processing script
            print("  Step 1: Running segmentation script...")
            script_success = run_segmentation_script(script_path, folder)

            if not script_success:
                print(f"  [ERROR] Script finished with an error")
                failed += 1
                continue

            print(f"  [OK] Script executed successfully")

            # 2. Check if the final file was created
            final_seg = folder / "combined_result.nii.gz"
            if not final_seg.exists():
                print(f"  [ERROR] combined_result.nii.gz was not created")
                failed += 1
                continue

            print(f"  [OK] Segmentation file created")

            # 3. Find the MRI file
            mri_file = find_mri_file(folder)
            if not mri_file:
                print(f"  [ERROR] MRI file not found")
                failed += 1
                continue

            print(f"  [OK] MRI file found: {mri_file.name}")

            # 4. Compute metrics for each structure
            print("  Step 2: Computing metrics for each structure...")
            structures_metrics = compute_metrics_per_structure(final_seg, mri_file)

            if structures_metrics:
                # Add folder info to each structure
                for metrics in structures_metrics:
                    metrics['folder'] = folder.name
                    all_results.append(metrics)

                successful += 1
                print(f"  [OK] Structures processed: {len(structures_metrics)}")

                # Show the first 5 structures
                print(f"  Example structures:")
                for j, m in enumerate(structures_metrics[:5]):
                    print(f"    Structure {m['structure_number']}: "
                          f"intensity={m['mean_intensity']:.2f}, "
                          f"volume={m['volume_ml']:.2f} ml")
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

    # Save results
    print(f"\n{'='*70}")
    print("SAVING RESULTS")
    print(f"{'='*70}")

    if all_results:
        df = pd.DataFrame(all_results)

        # Reorder columns for convenience
        df = df[['folder', 'structure_number', 'mean_intensity',
                 'volume_ml', 'volume_mm3', 'voxel_count']]

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        try:
            # Save full results
            full_file = base_path / f"all_structures_results_{timestamp}.xlsx"
            df.to_excel(full_file, index=False)
            print(f"[OK] Full results: {full_file}")

            # Save summary by structure (average across all folders)
            summary = df.groupby('structure_number').agg({
                'mean_intensity': ['mean', 'std', 'min', 'max', 'count'],
                'volume_ml': ['mean', 'std', 'min', 'max']
            }).round(4)

            summary_file = base_path / f"structures_summary_{timestamp}.xlsx"
            summary.to_excel(summary_file)
            print(f"[OK] Summary by structure: {summary_file}")

            # Save a pivot table per folder
            pivot_mean = df.pivot(index='folder', columns='structure_number',
                                   values='mean_intensity')
            pivot_mean_file = base_path / f"pivot_mean_intensity_{timestamp}.xlsx"
            pivot_mean.to_excel(pivot_mean_file)
            print(f"[OK] Pivot table (mean intensities): {pivot_mean_file}")

            pivot_volume = df.pivot(index='folder', columns='structure_number',
                                     values='volume_ml')
            pivot_volume_file = base_path / f"pivot_volume_{timestamp}.xlsx"
            pivot_volume.to_excel(pivot_volume_file)
            print(f"[OK] Pivot table (volumes): {pivot_volume_file}")

        except Exception as e:
            print(f"[ERROR] Could not save to Excel: {e}")
            # Save to CSV as a fallback
            csv_file = base_path / f"all_structures_results_{timestamp}.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f"[OK] CSV file saved: {csv_file}")

        print(f"\n{'='*70}")
        print("STATISTICS")
        print(f"{'='*70}")
        print(f"Total folders: {len(folders)}")
        print(f"Successfully processed folders: {successful}")
        print(f"Failed: {failed}")
        print(f"Total structures: {len(df)}")
        print(f"Unique structures: {df['structure_number'].nunique()}")
        print(f"Processing time: {elapsed_time/60:.1f} minutes")

        # Statistics by structure
        print(f"\nStatistics by structure (average across all folders):")
        print(f"  Mean intensity: {df['mean_intensity'].mean():.2f} +- {df['mean_intensity'].std():.2f}")
        print(f"  Mean volume: {df['volume_ml'].mean():.2f} +- {df['volume_ml'].std():.2f} ml")

    else:
        print("[ERROR] No data to save")

    print(f"\n{'='*70}")
    print("PROCESSING COMPLETE")
    print(f"{'='*70}")


def test_single_folder(base_path, script_path):
    """Test on a single folder"""
    base_path = Path(base_path)

    folders = [f for f in base_path.iterdir() if f.is_dir()]

    if not folders:
        print("No folders to test")
        return

    print("\nAvailable folders:")
    for i, f in enumerate(folders[:10], 1):
        print(f"  {i}. {f.name}")

    try:
        choice = int(input("\nChoose a folder number to test: ")) - 1
        if 0 <= choice < len(folders):
            folder = folders[choice]
        else:
            print("Invalid number, using the first folder")
            folder = folders[0]
    except:
        print("Invalid input, using the first folder")
        folder = folders[0]

    print(f"\n{'='*70}")
    print(f"TEST ON FOLDER: {folder.name}")
    print(f"{'='*70}")

    print("\n1. Running the processing script...")
    success = run_segmentation_script(script_path, folder)

    if success:
        print("[OK] Script executed successfully")

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
                print(f"  [ERROR] {filename} - not created")

        final_seg = folder / "combined_result.nii.gz"
        mri_file = find_mri_file(folder)

        if final_seg.exists() and mri_file:
            print("\n3. Computing metrics for structures...")
            metrics = compute_metrics_per_structure(final_seg, mri_file)
            if metrics:
                print(f"  [OK] Structures found: {len(metrics)}")
                print(f"  Example of the first 5 structures:")
                for m in metrics[:5]:
                    print(f"    Structure {m['structure_number']}: "
                          f"intensity={m['mean_intensity']:.2f}, "
                          f"volume={m['volume_ml']:.2f} ml")
            else:
                print("  [ERROR] Could not compute metrics")
    else:
        print("[ERROR] Script did not run successfully")


def ask_for_path(prompt_text):
    """Ask the user for a path, stripping quotes and extra whitespace"""
    raw = input(prompt_text).strip()
    # Remove surrounding quotes if the user pasted a quoted path
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1]
    return raw


if __name__ == "__main__":
    print("="*70)
    print("MRI SEGMENTATION PROCESSING AUTOMATION")
    print("="*70)

    # ========== ASK THE USER FOR PATHS ==========
    base_path = ask_for_path("Enter the path to the folder with MRI data (subfolders): ")
    script_path = ask_for_path("Enter the path to the processing script (.py): ")
    # ==============================================

    print("\n" + "="*70)
    print(f"Data folder: {base_path}")
    print(f"Processing script: {script_path}")

    if not Path(base_path).exists():
        print(f"\n[ERROR] Folder does not exist!")
        input("\nPress Enter to exit...")
        sys.exit(1)

    if not Path(script_path).exists():
        print(f"\n[ERROR] Script not found!")
        input("\nPress Enter to exit...")
        sys.exit(1)

    print("\nCHOOSE A MODE:")
    print("1 - Test on a single folder")
    print("2 - Process all folders")

    mode = input("Your choice (1 or 2): ").strip()

    if mode == "1":
        test_single_folder(base_path, script_path)
    elif mode == "2":
        process_all_folders(base_path, script_path)
    else:
        print("Invalid choice")

    input("\nPress Enter to exit...")
