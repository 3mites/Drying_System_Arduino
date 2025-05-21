import math

class MoistureEstimator:
    def __init__(self, temperature, relative_humidity):
        self.temperature = temperature
        self.relative_humidity = relative_humidity
        self.initial_moisture = 28  # Initial moisture content (%)
        self.C = 57.286
        self.N = 1.544
        self.K_base = 0.0002653

    def calculate_emc(self):
        rh_ratio = self.relative_humidity / 100
        numerator = -math.log(1 - rh_ratio)
        denominator = self.K_base * (self.temperature + self.C)
        return (numerator / denominator) ** (1 / self.N)

    def calculate_heat_constant(self):
        kelvin_temp = self.temperature + 273.15
        return self.K_base * math.exp(-1.544 / kelvin_temp)

    def get_drying_time_seconds(self):
        emc = self.calculate_emc()
        k = self.calculate_heat_constant()

        A = 0
        while True:
            mc_t = self.initial_moisture * math.exp(-k * A) + emc * (1 - math.exp(-k * A))
            if 13.0 <= mc_t <= 14.0:
                return A  # total seconds
            A += 1

estimator = MoistureEstimator(temperature=28, relative_humidity=52.08)
total_seconds = estimator.get_drying_time_seconds()
print(f"Total drying time: {total_seconds} seconds")
