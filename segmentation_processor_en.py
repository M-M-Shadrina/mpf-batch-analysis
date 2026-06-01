import nibabel as nib
import numpy as np
import sys
import gc
from pathlib import Path

def find_file_by_patterns(folder_path, patterns):
    """Find a file in a folder by a list of name patterns"""
    folder_path = Path(folder_path)
    
    for pattern in patterns:
        if '*' in pattern:
            files = list(folder_path.glob(pattern))
            if files:
                return files[0]
        else:
            test_path = folder_path / pattern
            if test_path.exists():
                return test_path
    return None

def find_main_segmentation(folder_path):
    """Find the main segmentation file (60+ structures)"""
    patterns = [
        "JHU_MNI_SS_WMPM_Type-III_MPF_Ranz_Sha.nii.gz",
        "JHU_MNI_SS_WMPM_Type-III_MPF_Ranz_Sha.nii",
        "JHU_MNI_SS_WMPM_Type-III_MPF_Ranz.nii.gz",
        "JHU_MNI_SS_WMPM_Type-III_MPF_Ranz.nii",
        "JHU_MNI_SS_WMPM_Type-III_MPFdev_Sha.nii.gz",
        "JHU_MNI_SS_WMPM_Type-III_MPFdev_Sha.nii",
        "JHU_MNI_SS_WMPM_Type-III_MPFdev.nii.gz",
        "JHU_MNI_SS_WMPM_Type-III_MPFdev.nii",
        "JHU_MNI_SS_WMPM_Type-III_MPF_Sha.nii.gz",
        "JHU_MNI_SS_WMPM_Type-III_MPF_Sha.nii",
        "JHU_MNI_SS_WMPM_Type-III_MPF.nii.gz",
        "JHU_MNI_SS_WMPM_Type-III_MPF.nii",
        "*WMPM*.nii.gz",
        "*WMPM*.nii",
        "*MPF*.nii.gz",
        "*MPF*.nii",
        "*JHU*.nii.gz",
        "*JHU*.nii"
    ]
    return find_file_by_patterns(folder_path, patterns)

def find_mask_segmentation(folder_path):
    """Find the segmentation mask file (white and grey matter)"""
    patterns = [
        "MPFuncor_coef_trim_seg.nii.gz",
        "MPFuncor_coef_trim_seg.nii",
        "MPFuncor_coef_trim_seg",
        "MPFuncor_transform_extr_seg.nii.gz",
        "MPFuncor_transform_extr_seg.nii",
        "MPFuncor_transform_extr_seg",
        "*_extr_seg*.nii.gz",
        "*_extr_seg*.nii",
        "*trim_seg*.nii.gz",
        "*trim_seg*.nii",
        "*_seg*.nii.gz",
        "*_seg*.nii"
    ]
    return find_file_by_patterns(folder_path, patterns)

def find_mri_file(folder_path):
    """Find the source MRI file"""
    patterns = [
        "MPFuncor_coef_transform.nii.gz",
        "MPFuncor_coef_transform.nii",
        "MPFuncor_coef_transform",
        "MPFuncor_transform.nii.gz",
        "MPFuncor_transform.nii",
        "MPFuncor_transform",
        "*MPFuncor*.nii.gz",
        "*MPFuncor*.nii",
        "*transform*.nii.gz",
        "*transform*.nii"
    ]
    return find_file_by_patterns(folder_path, patterns)

def find_lesions_file(folder_path):
    """Find the demyelination lesions file"""
    patterns = [
        "lesions.nii.gz",
        "lesions.nii",
        "lesion0.nii.gz",
        "lesion0.nii",
        "*lesion*.nii.gz",
        "*lesion*.nii",
    ]
    return find_file_by_patterns(folder_path, patterns)

def process_folder(folder_path):
    """Main processing function"""
    folder_path = Path(folder_path)
    
    print(f"Processing: {folder_path.name}")
    sys.stdout.flush()
    
    # 1. Find main segmentation (60+ structures)
    main_seg = find_main_segmentation(folder_path)
    if not main_seg:
        print(f"  [ERROR] Main segmentation file not found")
        print(f"  Files in folder: {[f.name for f in folder_path.iterdir() if f.is_file()]}")
        return False
    print(f"  [OK] Main segmentation: {main_seg.name}")
    
    # 2. Find segmentation mask (white and grey matter)
    mask_seg = find_mask_segmentation(folder_path)
    if not mask_seg:
        print(f"  [ERROR] Segmentation mask not found")
        print(f"  Files in folder: {[f.name for f in folder_path.iterdir() if f.is_file()]}")
        return False
    print(f"  [OK] Segmentation mask: {mask_seg.name}")
    
    # 3. Find source MRI file
    mri_file = find_mri_file(folder_path)
    if not mri_file:
        print(f"  [ERROR] MRI file not found")
        print(f"  Files in folder: {[f.name for f in folder_path.iterdir() if f.is_file()]}")
        return False
    print(f"  [OK] MRI file: {mri_file.name}")
    
    # 4. Find demyelination lesions file (optional)
    lesions_file = find_lesions_file(folder_path)
    if lesions_file:
        print(f"  [OK] Lesions file found: {lesions_file.name}")
    else:
        print(f"  [WARNING] Lesions file not found, lesion removal will be skipped")
    
    sys.stdout.flush()
    
    try:
        # ========== STEP 1: Remap main segmentation ==========
        print("  [1/6] Remapping main segmentation (swap labels 14-19 and 24-29)...")
        img_main = nib.load(str(main_seg))
        data_main = img_main.get_fdata().astype(np.int32)
        
        # Swap label values using temporary markers to avoid conflicts
        new_data = data_main.copy()
        del data_main
        
        new_data[new_data == 14] = 1014
        new_data[new_data == 15] = 1015
        new_data[new_data == 16] = 1016
        new_data[new_data == 17] = 1017
        new_data[new_data == 18] = 1018
        new_data[new_data == 19] = 1019
        
        new_data[new_data == 24] = 14
        new_data[new_data == 25] = 15
        new_data[new_data == 26] = 16
        new_data[new_data == 27] = 17
        new_data[new_data == 28] = 18
        new_data[new_data == 29] = 19
        
        new_data[new_data == 1014] = 24
        new_data[new_data == 1015] = 25
        new_data[new_data == 1016] = 26
        new_data[new_data == 1017] = 27
        new_data[new_data == 1018] = 28
        new_data[new_data == 1019] = 29
        
        remapped_path = folder_path / "remapped.nii.gz"
        nib.save(nib.Nifti1Image(new_data.astype(np.int16), img_main.affine), str(remapped_path))
        print(f"      [OK] Created: remapped.nii.gz")
        
        del new_data
        gc.collect()
        
        # ========== STEP 2: Split into GM and WM ==========
        print("  [2/6] Splitting into GM (labels 1-19) and WM (labels 20+)...")
        img_remap = nib.load(str(remapped_path))
        mask_data = img_remap.get_fdata()
        affine = img_remap.affine
        header = img_remap.header
        
        mask_rounded = np.round(mask_data).astype(int)
        del mask_data
        gc.collect()
        
        mask_gm = np.zeros_like(mask_rounded, dtype=np.int16)
        mask_wm = np.zeros_like(mask_rounded, dtype=np.int16)
        
        # GM: labels 1-19
        gm_mask = (mask_rounded >= 1) & (mask_rounded <= 19)
        mask_gm[gm_mask] = mask_rounded[gm_mask]
        
        # WM: labels 20+
        wm_mask = mask_rounded >= 20
        mask_wm[wm_mask] = mask_rounded[wm_mask]
        
        del mask_rounded
        gc.collect()
        
        output_gm = folder_path / "remapped_GM.nii.gz"
        output_wm = folder_path / "remapped_WM.nii.gz"
        
        nib.save(nib.Nifti1Image(mask_gm.astype(np.int16), affine, header), str(output_gm))
        nib.save(nib.Nifti1Image(mask_wm.astype(np.int16), affine, header), str(output_wm))
        print(f"      [OK] Created: remapped_GM.nii.gz")
        print(f"      [OK] Created: remapped_WM.nii.gz")
        
        del mask_gm, mask_wm
        gc.collect()
        
        # ========== STEP 3: Process segmentation mask (recode 2->1, 3->2) ==========
        print("  [3/6] Processing segmentation mask (recode 2->1, 3->2)...")
        img_mask = nib.load(str(mask_seg))
        mask_data = img_mask.get_fdata()
        affine_mask = img_mask.affine
        header_mask = img_mask.header
        
        processed_mask = np.zeros_like(mask_data, dtype=np.int16)
        processed_mask[mask_data == 2] = 1
        processed_mask[mask_data == 3] = 2
        
        del mask_data
        gc.collect()
        
        processed_mask_path = folder_path / "processed_mask.nii"
        nib.save(nib.Nifti1Image(processed_mask.astype(np.int16), affine_mask, header_mask), str(processed_mask_path))
        print(f"      [OK] Created: processed_mask.nii")
        
        del processed_mask
        gc.collect()
        
        # ========== STEP 4: Multiply WM by processed_mask ==========
        print("  [4/6] Multiplying remapped_WM.nii.gz by processed_mask.nii...")
        
        img_wm = nib.load(str(output_wm))
        img_processed_mask = nib.load(str(processed_mask_path))
        
        data_wm = img_wm.get_fdata().astype(np.int32)
        data_mask = img_processed_mask.get_fdata().astype(np.int32)
        
        if data_wm.shape != data_mask.shape:
            print(f"      Warning: shape mismatch, cropping to minimum size")
            min_shape = tuple(min(d1, d2) for d1, d2 in zip(data_wm.shape, data_mask.shape))
            data_wm = data_wm[:min_shape[0], :min_shape[1], :min_shape[2]]
            data_mask = data_mask[:min_shape[0], :min_shape[1], :min_shape[2]]
        
        segmented_cortex = data_wm * data_mask
        
        segmented_cortex_path = folder_path / "segmented_cortex.nii"
        nib.save(nib.Nifti1Image(segmented_cortex.astype(np.int32), img_wm.affine, img_wm.header), str(segmented_cortex_path))
        print(f"      [OK] Created: segmented_cortex.nii")
        
        del data_wm, data_mask, segmented_cortex
        gc.collect()
        
        # ========== STEP 5: Add segmented_cortex to GM ==========
        print("  [5/6] Adding segmented_cortex.nii to remapped_GM.nii.gz...")
        
        img_cortex = nib.load(str(segmented_cortex_path))
        img_gm = nib.load(str(output_gm))
        
        data_cortex = img_cortex.get_fdata().astype(np.int32)
        data_gm = img_gm.get_fdata().astype(np.int32)
        
        if data_cortex.shape != data_gm.shape:
            min_shape = tuple(min(d1, d2) for d1, d2 in zip(data_cortex.shape, data_gm.shape))
            data_cortex = data_cortex[:min_shape[0], :min_shape[1], :min_shape[2]]
            data_gm = data_gm[:min_shape[0], :min_shape[1], :min_shape[2]]
        
        result_combined = data_cortex + data_gm
        
        del data_cortex, data_gm
        gc.collect()
        
        # ========== STEP 6: Remove demyelination lesions ==========
        if lesions_file:
            print("  [6/6] Removing demyelination lesions...")
            
            img_lesions = nib.load(str(lesions_file))
            lesions_data = img_lesions.get_fdata()
            
            if result_combined.shape != lesions_data.shape:
                print(f"      Warning: shape mismatch, cropping to minimum size")
                min_shape = tuple(min(d1, d2) for d1, d2 in zip(result_combined.shape, lesions_data.shape))
                result_combined = result_combined[:min_shape[0], :min_shape[1], :min_shape[2]]
                lesions_data = lesions_data[:min_shape[0], :min_shape[1], :min_shape[2]]
            
            # Identify lesion voxels (values > 0) and zero them out
            lesions_mask = lesions_data > 0
            lesions_count = np.sum(lesions_mask)
            print(f"      Lesion voxels found: {lesions_count}")
            
            before_nonzero = np.sum(result_combined > 0)
            result_combined[lesions_mask] = 0
            after_nonzero = np.sum(result_combined > 0)
            
            print(f"      Voxels before removal: {before_nonzero}")
            print(f"      Voxels after removal:  {after_nonzero}")
            print(f"      Voxels removed:        {before_nonzero - after_nonzero}")
            
            del lesions_data, lesions_mask
            gc.collect()
        else:
            print("  [6/6] Skipped: lesions file not found")
        
        # Save final result
        final_result = folder_path / "combined_result.nii.gz"
        nib.save(nib.Nifti1Image(result_combined.astype(np.int32), img_cortex.affine, img_cortex.header), str(final_result))
        print(f"      [OK] Created: combined_result.nii.gz")
        
        del result_combined
        gc.collect()
        
        print(f"  [OK] Processing of {folder_path.name} complete!")
        return True
        
    except Exception as e:
        print(f"  [ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return False


if __name__ == "__main__":
    print("Script started")
    sys.stdout.flush()
    
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
        print(f"Processing folder: {folder_path}")
        sys.stdout.flush()
        
        success = process_folder(folder_path)
        print(f"Result: {'SUCCESS' if success else 'ERROR'}")
        sys.stdout.flush()
        
        sys.exit(0 if success else 1)
    else:
        print("No arguments provided — please specify a folder path")
        sys.stdout.flush()
        sys.exit(1)
ENDOFFILE
