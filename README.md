# bladeacer's Obsidian Snippets Collection
This repository is a collection of CSS snippets for the note taking application Obsidian.

## Why another snippet collection?
There are quite a few snippet collections by the Obsidian community. Here are
some of the reasons I decided to make my own:
- I do not really know where to begin to contribute to all of them
- I wish to showcase some of the more niche snippets I found or made,
especially those from my theme flexcyon.

## Snippets in this repository
### From flexcyon
[View this directory for the snippets](./snippets/flexcyon)
- Accessibility
- ASCII Art in new tab
- Vim Mode Status
- Callouts
  - Callout color
  - Callout extended color
  - No Icon/Background
  - Horizontal/vertical alignment
  - Vertical alignment
  - Text transform
  - and many others...

### Extracting your own snippets
Enclose your snippet(s) of interest like this

```css
/* obsi-snip-coll start */
body {
    font-size: 1.2rem;
}
/* obsi-snip-coll end */

```

Make use of the [extraction script](extract-snippets.py).

Ensure you have Python installed (check with `which python`, [install it on Windows](https://www.python.org/downloads/))

Follow the supported .env formats to configure target sources:
- [Single source](.env.dev)
- [Multiple sources](.env.dev-2)

```sh
cp .env.dev-2 .env
vim .env
```

Set permissions if you are on Linux.

```sh
sudo chmod +x ./extract-snippets.py
```

Run the script.
```sh
./extract-snippets.py
```

## Recommended snippets to install
- efemkay / [Obsidian Modular CSS Layout](https://github.com/efemkay/obsidian-modular-css-layout#wide-views)
- HandaArchitect / [obsidian-banner-snippet](https://github.com/HandaArchitect/obsidian-banner-snippet)

## Other snippet collections
<details>
  <summary>Click to expand/collapse</summary>

- [#appearance](https://discord.com/channels/686053708261228577/702656734631821413) - Obsidian discord
- [Obsidian CSS Quick Guide](https://forum.obsidian.md/t/obsidian-css-quick-guide/58178) (forum) (mostly about using the inspector) -
- [CSS Variables at Obsidian Dev Docs](https://docs.obsidian.md/Reference/CSS+variables/CSS+variables)
- replete / [obsidian-minimal-theme-css-snippets](https://github.com/replete/obsidian-minimal-theme-css-snippets)
- SlRvb's [snippets collection](https://github.com/SlRvb/Obsidian--ITS-Theme/tree/main/Snippets) | [Guide](https://publish.obsidian.md/slrvb-docs/ITS+Theme/ITS+Theme)
- zamsyt / [obsidian-snippets](https://github.com/zamsyt/obsidian-snippets)
- ElsaTam /  [Obsidian-Stuff](https://github.com/ElsaTam/Obsidian-Stuff)
- KuiyueRO / [Obsidian-Miner](https://github.com/KuiyueRO/Obsidian-Miner)
- sailKiteV / [Obsidian-Snippets-and-Demos](https://github.com/sailKiteV/Obsidian-Snippets-and-Demos?tab=readme-ov-file)
- TfTHacker / [DashboardPlusPlus](https://github.com/TfTHacker/DashboardPlusPlus)
- eb2ai / [My-Checklists-and-Icons](https://github.com/eb2ai/My-Checklists-and-Icons?tab=readme-ov-file)
- xhuajin / [obsidian-sidenote-callout](https://github.com/xhuajin/obsidian-sidenote-callout/tree/main)
</details>

## Credits
- r-u-s-h-i-k-e-s-h / [Obsidian CSS Snippets](https://github.com/r-u-s-h-i-k-e-s-h/Obsidian-CSS-Snippets)
- The wonderful `#appearance` community on the Obsidian Members' Group Discord
