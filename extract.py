from copy import deepcopy
import json
from os import path
from pdf2image import convert_from_path
import cv2
import numpy as np
from PIL import Image
from config import cop_data


def render_borders(image, hlines, vlines):
    blank = np.zeros(image.shape, np.uint8) + 255
    for hline in hlines:
        start, end = hline
        blank[start:end, :] = 0
    for vline in vlines:
        start, end = vline
        blank[:, start:end] = 0
    return Image.fromarray(blank)


def get_borders(image):
    # Convert the image to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Create a binary image
    _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)

    # Get the horizontal and vertical lines
    vsum = binary.sum(axis=0)
    hsum = binary.sum(axis=1)
    hlines = np.where(hsum < 0.4 * (hsum.max() - hsum.min()))[0]
    vlines = np.where(vsum < 0.4 * (vsum.max() - vsum.min()))[0]

    # Group adjacent lines into spans
    hline_spans = []
    current = []
    for i in range(0, len(hlines)):
        if len(current) == 0 or hlines[i] - current[-1] < 20:
            current.append(hlines[i])
        else:
            hline_spans.append([current[0], current[-1] + 1])
            current = [hlines[i]]
    hline_spans.append([current[0], current[-1] + 1])
    vline_spans = []
    current = []
    for i in range(0, len(vlines)):
        if len(current) == 0 or vlines[i] - current[-1] < 10:
            current.append(vlines[i])
        else:
            vline_spans.append([current[0], current[-1] + 1])
            current = [vlines[i]]
    vline_spans.append([current[0], current[-1] + 1])

    return hline_spans[1:], vline_spans


def test_get_borders(page_images):
    for event in cop_data["events"]:
        for eg in event["eg"]:
            first, last = eg["page_range"]
            for page_num in range(first, last + 1):
                page = page_images[page_num - 1]
                hlines, vlines = get_borders(np.array(page))
                assert len(hlines) == 5
                assert len(vlines) == 7


def get_boxes(page):
    hlines, vlines = get_borders(page)
    imgs = []
    for i in range(1, len(hlines)):
        for j in range(1, len(vlines)):
            y1 = hlines[i-1][1]
            y2 = hlines[i][0]
            x1 = vlines[j-1][1]
            x2 = vlines[j][0]
            img = page[y1:y2, x1:x2]
            imgs.append(img)

    img_sums = [img.sum() for img in imgs]
    threshold = np.mean(img_sums)  # + 0.2 * np.std(img_sums)
    return [{"img": img, "is_empty": img.sum() > threshold} for img in imgs]


def masked_fill_pct(img, box_pct, color=255):
    x1_pct, y1_pct, x2_pct, y2_pct = box_pct
    x1 = int(x1_pct * img.shape[1])
    y1 = int(y1_pct * img.shape[0])
    x2 = int(x2_pct * img.shape[1])
    y2 = int(y2_pct * img.shape[0])
    img[y1:y2, x1:x2] = color
    return img


def load_and_parse():
    page_images = convert_from_path('data/en_ 2022-2024 MAG CoP.pdf', 200)
    test_get_borders(page_images)
    skills = []
    values = "ABCDEF"
    for event in cop_data["events"]:
        for egr in event["eg"]:
            if event["acronym"] == "VT":
                box_num = 100 * egr["num"]
            else:
                box_num = 0
            first, last = egr["page_range"]
            for p in range(first - 1, last):
                page_arr = np.array(page_images[p])
                for box in get_boxes(page_arr):
                    box_num += 1
                    if (box["is_empty"]):
                        continue
                    id = event["acronym"] + "-" + \
                        str(egr["num"]) + "-" + str(box_num)
                    filename = id + ".png"

                    img_proc = box["img"].copy()
                    skill = egr.get("skills", {}).get(box_num, {})
                    # mask out the value
                    value_bbox = skill.get("value_bbox")
                    if (value_bbox):
                        masked_fill_pct(img_proc, value_bbox)
                    # mask out the box number
                    mask = [0, 0, 12*len(str(box_num)), 20]
                    x1, y1, x2, y2 = mask
                    img_proc[y1:y2, x1:x2] = 255

                    value = skill.get("value") or values[(
                        box_num - 1) % len(values)]
                    skills.append({
                        "id": id,
                        "event": event["name"],
                        "event_short": event["short"],
                        "event_acronym": event["acronym"],
                        "eg": egr["name"],
                        "eg_num": egr["num"],
                        "box_num": box_num,
                        "value": value,
                        "image_filename": filename,
                        "image_raw": box["img"],
                        "image_processed": img_proc,
                        "page": p,
                    })
    return skills


def save(skills):
    persisted_skills = deepcopy(skills)
    img_dir_raw = "data/img/raw/"
    img_dir_proc = "data/img/masked/"
    for skill in persisted_skills:
        cv2.imwrite(
            path.join(img_dir_raw, skill["image_filename"]), skill["image_raw"])
        cv2.imwrite(
            path.join(img_dir_proc, skill["image_filename"]), skill["image_processed"])
        del skill["image_raw"]
        del skill["image_processed"]
    with open("data/skills.json", "w") as f:
        json.dump(persisted_skills, f, indent=2)


if __name__ == "__main__":
    save(load_and_parse())
