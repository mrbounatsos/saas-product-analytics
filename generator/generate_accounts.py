import numpy as np

def monthly_signup_probabilities(
    n_months: int,
    growth_rate: float
)-> np.ndarray:

    # Generate month indices starting at zero
    month_indices = np.arange(n_months)

    # Calculate a growth weight for each month using the formula above.
    growth_weight = (1+ growth_rate)**month_indices 

    # Normalize those weights into probabilities.
    probabilities = growth_weight / growth_weight.sum()
    
    return probabilities

def main():
    result = monthly_signup_probabilities(12, 0.02)
    print(result)

if __name__ == "__main__":
    main()