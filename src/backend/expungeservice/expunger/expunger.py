from typing import Set, List, Iterator

from more_itertools import flatten

from expungeservice.expunger.analyzers.time_analyzer import TimeAnalyzer
from expungeservice.expunger.charges_summarizer import ChargesSummarizer
from expungeservice.models.charge import Charge
from expungeservice.models.disposition import DispositionStatus
from expungeservice.models.record import Record


class Expunger:
    """
    The TimeAnalyzer is probably the last major chunk of non-functional code.
    We mutate the charges in the record directly to add time eligibility information.
    Hence, for example, it is unsafe to deepcopy any elements in the "chain" stemming from record
    including closed_charges, charges, self.charges_with_summary.
    """

    def __init__(self, record: Record):
        self.record = record
        analyzable_charges = Expunger._without_skippable_charges(self.record.charges)
        self.charges_with_summary = ChargesSummarizer.summarize(analyzable_charges)

    def run(self) -> bool:
        """
        Evaluates the expungement eligibility of a record.

        :return: True if there are no open cases; otherwise False
        """
        open_cases = [case for case in self.record.cases if not case.closed()]
        if len(open_cases) > 0:
            case_numbers = ",".join([case.case_number for case in open_cases])
            self.record.errors += [
                f"All charges are ineligible because there is one or more open case: {case_numbers}. Open cases with valid dispositions are still included in time analysis. Otherwise they are ignored, so time analysis may be inaccurate for other charges."
            ]
        self.record.errors += self._build_disposition_errors(self.record.charges)
        TimeAnalyzer.evaluate(self.charges_with_summary)
        return len(open_cases) == 0

    @staticmethod
    def _without_skippable_charges(charges: Iterator[Charge]):
        return [charge for charge in charges if not charge.skip_analysis() and charge.disposition]

    @staticmethod
    def _build_disposition_errors(charges: List[Charge]):
        record_errors = []
        cases_with_missing_disposition, cases_with_unrecognized_disposition = Expunger._filter_cases_with_errors(
            charges
        )
        if cases_with_missing_disposition:
            record_errors.append(Expunger._build_disposition_error_message(cases_with_missing_disposition, "a missing"))
        if cases_with_unrecognized_disposition:
            record_errors.append(
                Expunger._build_disposition_error_message(cases_with_unrecognized_disposition, "an unrecognized")
            )
        return record_errors

    @staticmethod
    def _filter_cases_with_errors(charges: List[Charge]):
        cases_with_missing_disposition: Set[str] = set()
        cases_with_unrecognized_disposition: Set[str] = set()
        for charge in charges:
            if not charge.skip_analysis():
                case_number = charge.case()().case_number
                if not charge.disposition and charge.case()().closed():
                    cases_with_missing_disposition.add(case_number)
                elif charge.disposition and charge.disposition.status == DispositionStatus.UNRECOGNIZED:
                    cases_with_unrecognized_disposition.add(f"{case_number}: {charge.disposition.ruling}")
        return cases_with_missing_disposition, cases_with_unrecognized_disposition

    @staticmethod
    def _build_disposition_error_message(error_cases: Set[str], disposition_error_name: str):
        if len(error_cases) == 1:
            error_message = f"""Case {error_cases.pop()} has a charge with {disposition_error_name} disposition.
This might be an error in the OECI database. Time analysis is ignoring this charge and may be inaccurate for other charges."""
        else:
            cases_list_string = ", ".join(error_cases)
            error_message = f"""The following cases have charges with {disposition_error_name} disposition.
This might be an error in the OECI database. Time analysis is ignoring these charges and may be inaccurate for other charges.
Case numbers: {cases_list_string}"""
        return error_message
