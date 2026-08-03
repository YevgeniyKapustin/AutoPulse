"""Pricer-domain exceptions."""


class PricingNotFoundError(LookupError):
    def __init__(self, external_id: str) -> None:
        self.external_id = external_id
        super().__init__(f"Pricing result not found: {external_id}")
