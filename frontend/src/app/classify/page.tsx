"use client";

import dynamic from "next/dynamic";
import { SonarPing } from "@/components/animations";
import { IconCamera, IconMicrophone } from "@/components/icons/MarineIcons";

const PhotoClassifier = dynamic(
  () => import("@/components/PhotoClassifier"),
  {
    ssr: false,
    loading: () => (
      <div className="flex flex-col items-center gap-2 py-8">
        <SonarPing size={64} ringCount={3} active />
        <span className="text-xs text-ocean-400/70">Loading classifier…</span>
      </div>
    ),
  },
);

const AudioClassifier = dynamic(
  () => import("@/components/AudioClassifier"),
  {
    ssr: false,
    loading: () => (
      <div className="flex flex-col items-center gap-2 py-8">
        <SonarPing size={64} ringCount={3} active />
        <span className="text-xs text-ocean-400/70">Loading classifier…</span>
      </div>
    ),
  },
);

export default function ClassifyPage() {
  return (
    <>
      <main className="min-h-screen bg-abyss-950 px-4 pb-12 pt-20">
        {/* Header with Sonar Ping */}
        <div className="mx-auto mb-10 max-w-5xl text-center">
          <div className="mx-auto mb-6 flex justify-center">
            <SonarPing size={80} ringCount={3} active />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">
            Species Classification
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-slate-400">
            Upload a whale photograph or underwater audio recording. Our
            trained models will identify the species and show you similar
            look-alikes to double-check the result.
          </p>
        </div>

        {/* Side-by-side classifiers */}
        <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-2">
          {/* Photo classifier */}
          <section>
            <div className="mb-4 flex items-center gap-2">
              <IconCamera className="h-5 w-5 text-bioluminescent-400" />
              <div>
                <h2 className="text-sm font-semibold text-bioluminescent-400">
                  Photo Classification
                </h2>
                <p className="text-[11px] text-slate-500">
                  EfficientNet-B4 · 8 species · Happywhale-trained
                </p>
              </div>
            </div>
            <PhotoClassifier />
          </section>

          {/* Audio classifier */}
          <section>
            <div className="mb-4 flex items-center gap-2">
              <IconMicrophone className="h-5 w-5 text-bioluminescent-400" />
              <div>
                <h2 className="text-sm font-semibold text-bioluminescent-400">
                  Audio Classification
                </h2>
                <p className="text-[11px] text-slate-500">
                  XGBoost / CNN · 8 species · 4s segments
                </p>
              </div>
            </div>
            <AudioClassifier />
          </section>
        </div>

        {/* Model info — both always visible */}
        <div className="mx-auto mt-16 grid max-w-5xl gap-8 lg:grid-cols-2">
          <div className="rounded-xl border border-ocean-800 bg-abyss-900/40 p-6">
            <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
              About the Photo Model
            </h3>
            <div className="space-y-3 text-xs leading-relaxed text-slate-500">
              <p>
                <strong className="text-slate-300">Architecture:</strong>{" "}
                EfficientNet-B4 fine-tuned from ImageNet weights. 380×380
                input, differential learning rates (1e-4 head, 1e-5
                backbone), cosine annealing scheduler.
              </p>
              <p>
                <strong className="text-slate-300">Training data:</strong>{" "}
                ~20K filtered images from the Happywhale Kaggle dataset
                across 7 target species + &quot;other cetacean&quot;
                rejection class.
              </p>
              <p>
                <strong className="text-slate-300">Species:</strong> Right
                whale, humpback, fin, blue, minke, sei, killer whale, other
                cetacean.
              </p>
              <p>
                <strong className="text-slate-300">
                  Visual features used:
                </strong>{" "}
                Fluke patterns, dorsal fin shape, callosities, jaw
                coloring, saddle patches, flipper bands — learned
                automatically from mixed body views.
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-ocean-800 bg-abyss-900/40 p-6">
            <h3 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">
              About the Audio Model
            </h3>
            <div className="space-y-3 text-xs leading-relaxed text-slate-500">
              <p>
                <strong className="text-slate-300">Architecture:</strong>{" "}
                XGBoost on 64 acoustic features (97.9% accuracy) or CNN
                (ResNet18) on mel spectrograms (99.3% accuracy). Audio is
                segmented into 4-second windows with 2-second hop.
              </p>
              <p>
                <strong className="text-slate-300">Features:</strong> 20
                MFCCs (mean + std), spectral centroid/bandwidth/rolloff/
                flatness, spectral contrast (7 bands), ZCR, RMS energy,
                dominant frequency, temporal envelope statistics.
              </p>
              <p>
                <strong className="text-slate-300">Training data:</strong>{" "}
                452 audio files from Watkins Marine Mammal Sound Database +
                3 Zenodo datasets → 10,185 segments after segmentation.
              </p>
              <p>
                <strong className="text-slate-300">Species:</strong> Right
                whale, humpback, fin, blue, sperm, minke, sei, killer
                whale.
              </p>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
