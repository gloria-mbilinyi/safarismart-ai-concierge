import { ImageOff } from "lucide-react";
import { useState } from "react";

import { destinationPhotoFor } from "../lib/destinationPhotos";
import type { Destination } from "../types";

const responsiveSizes = "(max-width: 760px) calc(100vw - 28px), (max-width: 1220px) calc(50vw - 32px), 566px";

export function DestinationPhoto({ destination }: { destination: Destination }) {
  const [failed, setFailed] = useState(false);
  const photo = destinationPhotoFor(destination.slug);

  if (!photo || failed) {
    return (
      <div
        className="destination-photo-fallback"
        role="img"
        aria-label={`Photo unavailable for ${destination.name}`}
      >
        <ImageOff size={34} aria-hidden="true" />
        <span>Photo unavailable</span>
      </div>
    );
  }

  return (
    <figure className="destination-photo">
      <img
        src={photo.smallSrc}
        srcSet={`${photo.smallSrc} 640w, ${photo.largeSrc} 1280w`}
        sizes={responsiveSizes}
        width={1280}
        height={720}
        alt={photo.alt}
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
      />
      <figcaption>
        Photo:{" "}
        <a href={photo.sourceUrl} target="_blank" rel="noopener noreferrer">{photo.author}</a>
        <span aria-hidden="true"> · </span>
        <a href={photo.licenseUrl} target="_blank" rel="noopener noreferrer">{photo.licenseLabel}</a>
        <span> · cropped</span>
      </figcaption>
    </figure>
  );
}
