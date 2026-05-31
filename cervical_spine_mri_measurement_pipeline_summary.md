# Automatic Measurement Extraction from Cervical Spine MRI Segmentation

## Overall Idea

Use segmentation masks from a model such as TotalSpineSeg or nnU-Net and convert the segmented anatomy into geometric measurements.

Pipeline:

MRI -> segmentation masks -> contour extraction -> geometric computations -> anatomical measurements

Main structures:
- Vertebrae
- Intervertebral discs
- Spinal canal
- Spinal cord

Important:
All measurements must use MRI pixel spacing metadata to convert pixels into millimeters.

Formula:

real_mm = pixels × pixel_spacing

Without spacing conversion, measurements are not clinically meaningful.

---

# 1) Disc Height

Input:
Segmented intervertebral disc mask (example: C5-C6).

Basic method:

For every x-column inside the disc:

height(x) = bottom_y(x) - top_y(x)

Then:

Disc height = average(height(x))

Better anatomical method:

1. Extract upper disc contour.
2. Extract lower disc contour.
3. Fit smooth curves or lines.
4. Compute perpendicular distance between the curves.

This handles tilted cervical discs more accurately.

Metrics:
- Mean disc height
- Minimum disc height
- Central disc height

Evaluation:
- MAE in mm
- RMSE in mm
- Percentage error

---

# 2) AP Diameter (Anterior-Posterior Width)

Applicable to:
- Disc
- Spinal canal
- Vertebral body

Method:

For each row:

width(y) = posterior_x(y) - anterior_x(y)

Then compute:
- Central AP diameter
- Average AP diameter
- Minimum AP diameter

Usually central AP diameter is clinically important.

Evaluation:
- MAE in mm
- RMSE in mm

---

# 3) Lordosis / Cobb Angle

Input:
Segmented vertebrae (typically C2 to C7).

Method:

1. Detect vertebral endplate points.
2. Fit a line to:
   - inferior endplate of C2
   - inferior endplate of C7
3. Compute angle between the lines.

Formula:

theta = arctan(m1) - arctan(m2)

where m1 and m2 are line slopes.

Absolute value gives Cobb angle.

Evaluation:
- Mean absolute error in degrees
- RMSE in degrees

---

# 4) Canal Stenosis Metrics

Input:
Spinal canal mask and optionally spinal cord mask.

Possible measurements:
- Minimum canal AP diameter
- Canal cross-sectional area
- Cord area
- Cord/canal ratio

Example:

stenosis_ratio = cord_area / canal_area

Smaller canal diameter generally indicates greater stenosis.

Evaluation:
- MAE for diameter and area
- Classification metrics if stenosis grades are predicted

---

# 5) Degeneration Grading

Goal:
Predict degeneration severity.

Possible features:
- Disc height
- Disc area
- AP diameter
- MRI signal intensity
- Texture features
- Canal measurements

Pipeline:

features or MRI crop -> classifier -> degeneration grade

Possible grades:
- Normal
- Mild
- Moderate
- Severe

Possible models:
- CNN
- EfficientNet
- ResNet
- Small transformer

Evaluation:
- Accuracy
- Macro-F1
- Weighted-F1
- Cohen’s kappa
- Confusion matrix

---

# How Ground Truth Measurements Can Be Obtained

Doctors do not necessarily need to manually measure every disc.

Instead:

expert segmentation masks -> geometry algorithm -> reference measurements

Then:

predicted segmentation masks -> same geometry algorithm -> predicted measurements

Finally compare both.

This is a standard evaluation strategy.

---

# Segmentation Evaluation Metrics

Before measurement evaluation, segmentation quality should also be evaluated.

Metrics:
- Dice score
- IoU
- Hausdorff distance
- ASSD

Targets:
- Vertebra masks
- Disc masks
- Canal masks
- Cord masks

---

# Recommended Software Stack

Segmentation:
- TotalSpineSeg
- nnU-Net

Geometry and image processing:
- NumPy
- SciPy
- OpenCV
- scikit-image

Machine learning:
- PyTorch
- scikit-learn

---

# Strong Publishable Framing

MRI -> segmentation -> automatic anatomical measurements -> pathology assessment

Rather than presenting the project as only segmentation.

Possible title:

Fully Automated Cervical Spine MRI Segmentation and Quantitative Measurement Pipeline for Disc Height, Lordosis, and Canal Stenosis Assessment

