import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

class TemperatureFuzzyController:
    def __init__(self):
        # Define fuzzy variables
        self.temperature = ctrl.Antecedent(np.arange(25, 74, 1), 'temperature')
        self.humidity = ctrl.Antecedent(np.arange(0, 91, 1), 'humidity')
        self.temperature_adjustment = ctrl.Consequent(np.arange(25, 74, 1), 'temperature_adjustment')

        # Membership functions
        self.temperature['low'] = fuzz.trimf(self.temperature.universe, [25, 31, 36])
        self.temperature['warm'] = fuzz.trimf(self.temperature.universe, [34, 43, 60])
        self.temperature['high'] = fuzz.trimf(self.temperature.universe, [55, 70, 73])

        self.humidity['low'] = fuzz.trimf(self.humidity.universe, [0, 30, 40])
        self.humidity['average'] = fuzz.trimf(self.humidity.universe, [30, 50, 60])
        self.humidity['high'] = fuzz.trimf(self.humidity.universe, [55, 60, 90])

        self.temperature_adjustment['low'] = fuzz.trimf(self.temperature_adjustment.universe, [25, 31, 36])
        self.temperature_adjustment['warm'] = fuzz.trimf(self.temperature_adjustment.universe, [34, 43, 60])
        self.temperature_adjustment['high'] = fuzz.trimf(self.temperature_adjustment.universe, [55, 70, 73])

        # Define fuzzy rules
        rule1 = ctrl.Rule((self.temperature['high'] | self.temperature['warm'] | self.temperature['low']) & self.humidity['high'],
                          self.temperature_adjustment['low'])
        rule2 = ctrl.Rule(self.temperature['high'] & self.humidity['low'], self.temperature_adjustment['high'])
        rule3 = ctrl.Rule(self.temperature['high'] & self.humidity['average'], self.temperature_adjustment['warm'])
        rule4 = ctrl.Rule(self.temperature['warm'] & self.humidity['low'], self.temperature_adjustment['high'])
        rule5 = ctrl.Rule(self.temperature['warm'] & self.humidity['average'], self.temperature_adjustment['warm'])
        rule6 = ctrl.Rule(self.temperature['low'] & self.humidity['low'], self.temperature_adjustment['high'])
        rule7 = ctrl.Rule(self.temperature['low'] & self.humidity['average'], self.temperature_adjustment['warm'])

        # Control system
        self.control_system = ctrl.ControlSystem([rule1, rule2, rule3, rule4, rule5, rule6, rule7])
        self.simulation = ctrl.ControlSystemSimulation(self.control_system)

        # Keep track of last successful output
        self.last_output = None

    def compute_adjustment(self, temperature_value, humidity_value):
        try:
            self.simulation.input['temperature'] = temperature_value
            self.simulation.input['humidity'] = humidity_value
            self.simulation.compute()
            self.last_output = self.simulation.output['temperature_adjustment']
        except Exception as e:
            print(f"[Warning] Fuzzy computation error: {e}")
            print("[Info] Using last known good adjustment value.")
        return self.last_output

# Example usage:
if __name__ == "__main__":
    fuzzy_ctrl = TemperatureFuzzyController()
    test_values = [(35.3, 10), (80, 10), (36, 92)]  # Example test including edge/invalid inputs
    for temp, hum in test_values:
        adjustment = fuzzy_ctrl.compute_adjustment(temp, hum)
        print(f"Input Temperature: {temp}")
        print(f"Input Humidity: {hum}")
        print(f"Calculated Temperature Adjustment: {adjustment:.2f}" if adjustment is not None else "No valid adjustment.")
