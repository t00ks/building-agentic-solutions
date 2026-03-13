from dataclasses import dataclass

from core.models import Applicant, User


@dataclass
class AgentContextSchema:
    applicants: list[Applicant] | None
    user: User

    @property
    def applicants_formatted(self) -> str:
        """Format applicants information for display in prompts"""
        if not self.applicants:
            return "[NO APPLICANTS PROVIDED]"

        return "\n".join(
            [
                f"{idx + 1}. ID: {applicant.id} Name: {applicant.name}"
                for idx, applicant in enumerate(self.applicants)
            ]
        )
    
    @property
    def user_name(self) -> str:
        """Get the user's name or a default placeholder"""
        return self.user.name