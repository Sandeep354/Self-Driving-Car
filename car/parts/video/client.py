import cv2
from datetime import datetime
from car.Part import Part
import urllib.request
from car.utils import *


class Client(Part):

    def __init__(self, name, output_names, is_localhost, port=8091, url='/video', consecutive_no_image_count_threshold=150, is_verbose=False):
        super().__init__(
            name=name,
            is_localhost=is_localhost,
            port=port,
            url=url,
            output_names=output_names,
            is_verbose=is_verbose
        )
        # Need to define as None to avoid "does not exist bugs"
        self.frame = None
        self.stream = None
        try:
            print('{timestamp} - Attempting to open video stream...'.format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            ))
            self.open_stream()
            print('{timestamp} - Successfully opened video stream!'.format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            ))
        except:
            print('{timestamp} - Failed to open video stream!'.format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            ))

        """
        When the video is streaming well, about 1 of every 15
        iterations of the infinite loop produces an image. When
        the video is killed and there is nothing to show, the else
        part of the loop gets called consecutively indefinitely.
        I can avoid the zombie threads that take over my entire
        Tornado server (99% of CPU) if I check a consecutive
        failure count exceeding some arbitrarily high threshold
        """
        self.consecutive_no_image_count = 0
        self.consecutive_no_image_count_threshold = consecutive_no_image_count_threshold
        self.was_available = False

    # This automatically gets called in an infinite loop by the parent class, Part.py
    def request(self):
        if self.stream is None:
            self.open_stream()
        self.opencv_bytes += self.stream.read(1024)
        a = self.opencv_bytes.find(b'\xff\xd8')
        b = self.opencv_bytes.find(b'\xff\xd9')
        if a != -1 and b != -1:
            jpg = self.opencv_bytes[a:b + 2]
            self.opencv_bytes = self.opencv_bytes[b + 2:]
            frame = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if cv2.waitKey(1) == 27:
                exit(0)
            self.frame = frame
            self.consecutive_no_image_count = 0
            self.was_available = True
        else:
            if self.was_available:
                self.consecutive_no_image_count = 1
            else:
                self.consecutive_no_image_count += 1
            if self.consecutive_no_image_count > self.consecutive_no_image_count_threshold:
                self.stream = None  # Tells self.open_stream() to run
                """
                Resetting the count to 0 fixed a bug where the
                client could never recover, even after the
                ffmpeg server was brought up again. I suspect
                the bug occurred because I set the stream to None
                which would indicate that the stream needed to be
                reopened, and presumably it takes a few
                iterations to return an image. Resuming the count
                from where I left off would mean that I would
                have only once (or zero) chance of not exceeding
                the threshold
                """
                self.consecutive_no_image_count = 0
                raise Exception
            self.was_available = False

    # This is how the main control loop interacts with the part
    def _call(self):
        return self.frame

    def open_stream(self):
        self.stream = urllib.request.urlopen(self.endpoint)
        self.opencv_bytes = bytes()
