export type CuratedDestinationSlug =
  | "serengeti-national-park"
  | "ngorongoro-conservation-area"
  | "mount-kilimanjaro"
  | "zanzibar"
  | "tarangire-national-park";

export interface DestinationPhoto {
  smallSrc: string;
  largeSrc: string;
  alt: string;
  author: string;
  sourceUrl: string;
  licenseLabel: string;
  licenseUrl: string;
}

const imageRoot = "/images/destinations";

export const destinationPhotos: Record<CuratedDestinationSlug, DestinationPhoto> = {
  "serengeti-national-park": {
    smallSrc: `${imageRoot}/serengeti-national-park-640.webp`,
    largeSrc: `${imageRoot}/serengeti-national-park-1280.webp`,
    alt: "Zebras grazing beneath an acacia tree on the Serengeti plains",
    author: "Maximilian Staub",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:Zebras_in_Serengeti_National_Park_with_Acacia_tree.jpg",
    licenseLabel: "CC BY 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by/4.0/",
  },
  "ngorongoro-conservation-area": {
    smallSrc: `${imageRoot}/ngorongoro-conservation-area-640.webp`,
    largeSrc: `${imageRoot}/ngorongoro-conservation-area-1280.webp`,
    alt: "Wide view across the floor and rim of Ngorongoro Crater",
    author: "Zenith4237",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:Panorama_of_Ngorongoro_Crater.jpg",
    licenseLabel: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
  },
  "mount-kilimanjaro": {
    smallSrc: `${imageRoot}/mount-kilimanjaro-640.webp`,
    largeSrc: `${imageRoot}/mount-kilimanjaro-1280.webp`,
    alt: "Snow-streaked summit of Mount Kilimanjaro rising above clouds and plains",
    author: "Swiftaurora",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:Mt._Kilimanjaro_peak.jpg",
    licenseLabel: "CC BY-SA 4.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/4.0/",
  },
  zanzibar: {
    smallSrc: `${imageRoot}/zanzibar-640.webp`,
    largeSrc: `${imageRoot}/zanzibar-1280.webp`,
    alt: "Pongwe Beach in Zanzibar with turquoise water, white sand, and a palm tree",
    author: "Anton Zelenov",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:Pongwe_Beach_Zanzibar.jpg",
    licenseLabel: "CC BY-SA 3.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/3.0/",
  },
  "tarangire-national-park": {
    smallSrc: `${imageRoot}/tarangire-national-park-640.webp`,
    largeSrc: `${imageRoot}/tarangire-national-park-1280.webp`,
    alt: "Adult elephant and calf walking through Tarangire National Park",
    author: "Christoph Strässler",
    sourceUrl: "https://commons.wikimedia.org/wiki/File:Elephants,_Tarangire_National_Park,_Tanzania.jpg",
    licenseLabel: "CC BY-SA 2.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/2.0/",
  },
};

export const curatedDestinationSlugs = Object.freeze(
  Object.keys(destinationPhotos) as CuratedDestinationSlug[],
);

export function destinationPhotoFor(slug: string): DestinationPhoto | undefined {
  return destinationPhotos[slug as CuratedDestinationSlug];
}
