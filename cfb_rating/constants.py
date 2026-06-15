"""Constants for college football game evaluation."""

# Log-linear scaling coefficients
POINTS_LN_COEFF = 0.7492
YARDS_LN_COEFF = 52.089

# Intercepts for margin transforms
POINTS_INTERCEPT = -17.953
YARDS_INTERCEPT = -171.33

# Multipliers applied after the log-linear transform
YARDS_MULTIPLIER = 160.95865
POINTS_MULTIPLIER = 14.333

# Exponents for available-points scaling
POINTS_EXPONENT = 0.08184
YARDS_EXPONENT = 0.001693

# Blend weights for the combined game score (points + yards)
POINTS_WEIGHT = 0.3053
YARDS_WEIGHT = 0.6947

# Aliases matching source formula names (pointsLnCoeff, yardsLnCoeff, etc.)
pointsLnCoeff = POINTS_LN_COEFF
yardsLnCoeff = YARDS_LN_COEFF
pointsIntercept = POINTS_INTERCEPT
yardsIntercept = YARDS_INTERCEPT
yardsMultiplier = YARDS_MULTIPLIER
pointsMultiplier = POINTS_MULTIPLIER
pointsExponent = POINTS_EXPONENT
yardsExponent = YARDS_EXPONENT
pointsWeight = POINTS_WEIGHT
yardsWeight = YARDS_WEIGHT
