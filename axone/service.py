import logging
import time
from multiprocessing.shared_memory import SharedMemory
from typing import Optional

from axone.axone_struct import AxoneService
from axone.utils import generate_uuid


class Service:

    def __init__(
        self,
        service: AxoneService,
        rate: float = -1.0,
        source: Optional[str] = None,
    ) -> None:
        # Ensure that the service is an instance of AxoneStruct or that it has inherited from it
        if not isinstance(service, AxoneService):
            raise ValueError("The service should be an instance of AxoneService")

        self._service: AxoneService = service
        self._name: str = self._service.__class__.__name__
        self._source: str = source if source is not None else "unknown"
        self._rate: float = float(rate)
        self._last_update: float = 0

        self._uuid = generate_uuid(self._name)

        # Prepare common fields for the service
        self._service.source_ = self._source

        # Create a rolling counter for the service
        # This is a mean to match a request to an answer
        # When a request is made, the askee will wait for an answer mathcing the counter
        self._service.rolling_counter_ = 0

        # Create a shared memory for the service
        self._memory = SharedMemory(
            name=self._uuid,
            create=True,
            size=service.get_approximate_size(),
        )

        # TODO : Implement unlink, close, etc for the SHM
        logging.debug(f"Service {self._name} created with UUID {self._uuid}")

    @property
    def service(self) -> str:
        """The string representation of the service"""
        return self._service

    @property
    def name(self) -> str:
        """The service name of the publisher"""
        return self._name

    @property
    def request(self) -> AxoneService.AxoneRequest:
        """The request structure of the service"""
        return self._service.request_

    @property
    def answer(self) -> AxoneService.AxoneAnswer:
        """The answer structure of the service"""
        return self._service.answer_

    @property
    def rolling_counter(self) -> int:
        """The rolling counter of the service"""
        return self._service.rolling_counter_

    def fetch_request(self) -> Optional[AxoneService.AxoneRequest]:
        """Fetch the request of the service"""
        # Check that the memory is not empty
        if self._memory is None:
            return None
        if self._memory.buf is None:
            return None

        # Decode the memory
        encoded = bytes(self._memory.buf[:])
        self._service.decode(encoded)

        # Check if the request.source has been updated
        if self._service.source_ == "":
            return None

        # We have a new request
        return self._service.request_

    def reply_answer(self, answer: Optional[AxoneService.AxoneAnswer] = None) -> None:
        """Give an answer to the service"""
        if answer is not None:
            self._service.answer_ = answer

        # Give an answer to the service
        self._service.answer_.error_ = answer is not None
        self._service.answer_.timestamp_ = time.time()
        self._service.answer_.counter_ = self.rolling_counter

        # Increment the rolling counter
        self._service.rolling_counter_ += 1

        # Empty the request for the next one
        self._service.request_.source_ = ""
        self._service.request_.timestamp_ = time.time()
        self._service.request_.counter_ = self.rolling_counter

        # Encode the service
        encoded = self._service.encode()
        self._memory.buf[: len(encoded)] = encoded
