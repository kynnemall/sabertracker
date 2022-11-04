import os
import cv2
import argparse
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

# parameters for Hough Line detection
rho = 1                 # distance resolution in pixels of the Hough grid
theta = np.pi / 180     # angular resolution in radians of the Hough grid
threshold = 40          # minimum number of votes (intersections in Hough grid cell)
min_line_length = 25    # minimum number of pixels making up a line
max_line_gap = 10       # maximum gap in pixels between connectable line segments
WIDTH = 720             # width to resize the processed video to

def resize(img):
    return cv2.resize(img, (WIDTH, WIDTH))

def process_video(fname, save_video=False, savename=None, show_video=False, save_stats=False):
    if savename == None:
        savename = fname.split(".")[0] + "_tracking.avi"
    else:
        savename = "saber_tracking.avi"

    if save_video:
        # Initialize video writer to save the results
        out = cv2.VideoWriter(savename, cv2.VideoWriter_fourcc(*'XVID'), 30.0, 
                                 (WIDTH, WIDTH), True)

    cap = cv2.VideoCapture(fname)
    ret, frame = cap.read()
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    pbar = tqdm(total=total_frames)
    frame_num = 0

    if save_stats:
        output_path = savename.replace(".avi", "_data.parquet")
        data = {"frame" : [],
                "centroid_x" : [],
                "centroid_y" : [],
                "angle" : []}

    while ret:
        ret, frame = cap.read()
        # these channels were swapped compared to the notebook
        b = (frame[:, :, 2] > 200).astype(int)
        r = (frame[:, :, 0] > 220).astype(int)

        # convert to HSV for more masking options
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        v = (hsv[:, :, 2] > 210).astype(int)
        s = cv2.inRange(hsv[:, :, 1],  140, 175)

        # combine masks into one
        m1 = np.logical_and(b, s)
        m2 = np.logical_and(r, v)
        mask = (m1 + m2).astype(np.uint8)

        # Run Hough on edge detected image
        # Output "lines" is an array containing endpoints of detected line segments
        lines = cv2.HoughLinesP(mask, rho, theta, threshold, np.array([]),
            min_line_length, max_line_gap)

        # process lines
        if isinstance(lines, np.ndarray):
            for line in lines:
                for x1, y1, x2, y2 in line:                    
                    centroid = (int((x1 + x2) / 2), int((y1 + y2) / 2))
                    cv2.drawMarker(frame, centroid, (0, 255, 0),
                                   markerType=cv2.MARKER_CROSS, thickness=2)
                    if save_stats:
                        x_diff = x1 - x2
                        y_diff = y1 - y2
                        degrees = np.rad2deg(np.arctan(y_diff / x_diff))
                        data["frame"].append(frame_num)
                        data["centroid_x"].append(centroid[0])
                        data["centroid_y"].append(centroid[1])
                        data["angle"].append(degrees)
        if save_stats:
            df = pd.DataFrame(data)

            # Create a parquet table from your dataframe
            table = pa.Table.from_pandas(df)

            # Write direct to your parquet file
            pq.write_to_dataset(table, root_path=output_path)
            
            # reset data structure for appending
            data = {"frame" : [],
                    "centroid_x" : [],
                    "centroid_y" : [],
                    "angle" : []}

        resized = resize(frame)
        
        if show_video:
            cv2.imshow("Frame", resized)
        if save_video:
            out.write(resized)
        frame_num += 1
        pbar.update(1)

        key = cv2.waitKey(1)
        if key == ord('q'):
            break
        if key == ord('p'):
            cv2.waitKey(-1) # wait until any key is pressed

    cap.release()
    if save_video:
        out.release()
    if show_video:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # set up argparser for CLI
    parser = argparse.ArgumentParser()
    parser.add_argument("-sv", "--vidsave", action="store_true", default=False, help="Save video after processing")
    parser.add_argument("-sh", "--show", action="store_true", default=False, help="Show video while processing")
    parser.add_argument("-ss", "--tracksave", action="store_true", default=False, help="Save tracking data")
    parser.add_argument("-p", "--trackproc", action="store_true", default=False, help="Process tracking data")
    parser.add_argument("-f", "--filepath", default="test_video.mp4", help="Path to file")
    parser.add_argument("-sn", "--savename", default=None, help="Name for saving processed video file")
    args = parser.parse_args()
    print(args)

    if args.trackproc:
        # process tracking data
        pass
    else:
        # process video
        process_video(args.filepath, args.vidsave, args.savename, args.show, args.tracksave)