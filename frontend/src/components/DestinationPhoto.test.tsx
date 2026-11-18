/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  curatedDestinationSlugs,
  destinationPhotoFor,
  destinationPhotos,
} from "../lib/destinationPhotos";
import type { Destination } from "../types";
import { DestinationPhoto } from "./DestinationPhoto";

const serengeti: Destination = {
  id: "serengeti-id",
  name: "Serengeti National Park",
  slug: "serengeti-national-park",
  country: "Tanzania",
  region: "Mara",
  category: "national_park",
  description: "A test catalog destination.",
  is_featured: true,
};

afterEach(cleanup);

describe("destination photo catalog", () => {
  it("maps every curated destination to unique responsive local assets", () => {
    expect(curatedDestinationSlugs).toEqual([
      "serengeti-national-park",
      "ngorongoro-conservation-area",
      "mount-kilimanjaro",
      "zanzibar",
      "tarangire-national-park",
    ]);

    const paths = curatedDestinationSlugs.flatMap((slug) => {
      const photo = destinationPhotos[slug];
      expect(photo.alt.length).toBeGreaterThan(20);
      expect(photo.sourceUrl).toMatch(/^https:\/\/commons\.wikimedia\.org\//);
      expect(photo.licenseUrl).toMatch(/^https:\/\/creativecommons\.org\/licenses\//);
      expect(photo.smallSrc).toMatch(new RegExp(`/${slug}-640\\.webp$`));
      expect(photo.largeSrc).toMatch(new RegExp(`/${slug}-1280\\.webp$`));
      return [photo.smallSrc, photo.largeSrc];
    });

    expect(new Set(paths).size).toBe(paths.length);
  });

  it("does not invent a photo for an unknown catalog slug", () => {
    expect(destinationPhotoFor("future-destination")).toBeUndefined();
  });
});

describe("DestinationPhoto", () => {
  it("renders lazy responsive imagery with descriptive text and visible credit", () => {
    const photo = destinationPhotos["serengeti-national-park"];
    render(<DestinationPhoto destination={serengeti} />);

    const image = screen.getByRole("img", { name: photo.alt });
    expect(image.getAttribute("loading")).toBe("lazy");
    expect(image.getAttribute("decoding")).toBe("async");
    expect(image.getAttribute("src")).toBe(photo.smallSrc);
    expect(image.getAttribute("srcset")).toContain(`${photo.largeSrc} 1280w`);
    expect(screen.getByRole("link", { name: photo.author }).getAttribute("href")).toBe(photo.sourceUrl);
    expect(screen.getByRole("link", { name: photo.licenseLabel }).getAttribute("href")).toBe(photo.licenseUrl);
  });

  it("shows an accessible fallback when an image cannot load", () => {
    const photo = destinationPhotos["serengeti-national-park"];
    render(<DestinationPhoto destination={serengeti} />);

    fireEvent.error(screen.getByRole("img", { name: photo.alt }));

    expect(
      screen.getByRole("img", { name: "Photo unavailable for Serengeti National Park" }),
    ).toBeDefined();
    expect(screen.getByText("Photo unavailable")).toBeDefined();
  });

  it("uses the same fallback for an unmapped destination", () => {
    render(
      <DestinationPhoto
        destination={{ ...serengeti, name: "Future Destination", slug: "future-destination" }}
      />,
    );

    expect(
      screen.getByRole("img", { name: "Photo unavailable for Future Destination" }),
    ).toBeDefined();
  });
});
