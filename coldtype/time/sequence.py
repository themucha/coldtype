import re, math, copy
from enum import Enum

from coldtype.time import Timeable, Frame
from coldtype.time.easing import ease
from coldtype.time.timeline import Timeline

from coldtype.text import StyledString, Lockup, Graf, GrafStyle, Style
from coldtype.pens.datpen import DATPen, DATPens
from coldtype.color import *

from typing import Optional, Union, Callable, Tuple


class Marker(Timeable):
    def __init__(self, start, end, marker):
        # TODO super name= marker name?
        super().__init__(start, end, data=marker)


class ClipType(Enum):
    ClearScreen = "ClearScreen"
    NewLine = "NewLine"
    GrafBreak = "GrafBreak"
    Blank = "Blank"
    Isolated = "Isolated"
    JoinPrev = "JoinPrev"
    Meta = "Meta"


class ClipFlags(Enum):
    FadeIn = "FadeIn"
    FadeOut = "FadeOut"


class Clip(Timeable):
    def __init__(self, text, start, end, idx=None, track=0):
        self.idx = idx
        self.input_text = str(text)
        self.text = text
        self.start = start
        self.end = end

        self.styles = []
        self.style_clips = []
        self.position = 1
        self.joined = False
        self.joinPrev = None
        self.joinNext = None
        self.track = track
        self.group = None
        self.blank = False
        self.blank_height = 20
        self.inline_styles = []
        self.inline_data = {}
        self.flags = {}
        self.type = ClipType.Isolated

        if self.text.startswith("*"):
            self.text = self.text[1:]
            self.type = ClipType.ClearScreen
        elif self.text.startswith("≈"):
            self.text = self.text[1:]
            self.type = ClipType.NewLine
        elif self.text.startswith("¶"):
            self.text = self.text[1:]
            self.type = ClipType.GrafBreak
        elif self.text.startswith("+"):
            self.text = self.text[1:]
            self.type = ClipType.JoinPrev
        elif self.text.startswith("µ:"):
            self.type = ClipType.Meta
            self.text = self.text[2:]
        
        parts = self.text.split(":")
        inline_style_marker = parts.index("ß") if "ß" in parts else -1
        inline_data_marker = parts.index("∂") if "∂" in parts else -1

        if inline_style_marker > -1:
            self.inline_styles = parts[inline_style_marker+1].split(",")
        if inline_data_marker > -1:
            qs = [q.split("=") for q in parts[inline_data_marker+1].split("&")]
            for k, v in qs:
                self.inline_data[k] = eval(v)
        
        self.text = parts[0]

        #if "ß" in self.text:
        #    parts = self.text.split(":")
        #    self.text = parts[0]
        #    self.inline_styles = parts[-1].split(",")
        
        #self.text = self.text.replace("§", "\u200b")
        if self.text.startswith("§"):
            #self.text = "\u200b"
            self.text = self.text[1:]
            #self.type = ClipType.JoinPrev
            self.type = ClipType.NewLine
            self.blank = True
            try:
                self.blank_height = float(self.text.strip())
            except:
                pass
    
        if self.text.startswith("∫"):
            self.text = ""
            self.blank = True
        
        if not self.text:
            self.blank = True
            self.text = ""
        
        if self.text.startswith("ƒ"):
            r = r"^([0-9]+)ƒ"
            self.text = self.text[1:]
            value = 3
            match = re.match(r, self.text)
            if match:
                value = int(match[1])
                self.text = re.sub(r, "", self.text)
            self.flags[ClipFlags.FadeIn] = value
        
        elif self.text.endswith("ƒ"):
            self.flags[ClipFlags.FadeOut] = 3
        
        self.original_text = str(self.text)
    
    def addJoin(self, clip, direction):
        if direction == -1:
            self.joinPrev = clip
        elif direction == 1:
            self.joinNext = clip
    
    def joinStart(self):
        if self.joinPrev:
            return self.joinPrev.joinStart()
        else:
            return self.start
    
    def joinEnd(self):
        if self.joinNext:
            return self.joinNext.joinEnd()
        else:
            return self.end
    
    def textForIndex(self, index):
        txt = self.text
        try:
            txt = self.text.split("/")[index]
        except:
            txt = self.text.split("/")[-1]
        return txt, self.addSpace
    
    def style_matching(self, txt):
        try:
            return next(c for c in self.style_clips if txt in c.text)
        except StopIteration:
            return None

    def ftext(self):
        txt = self.text
        if self.type == ClipType.Isolated:
            return " " + txt
        else:
            return txt
    
    def fade(self, default_fade=5):
        if ClipFlags.FadeIn in self.flags:
            return self.flags[ClipFlags.FadeIn]
        else:
            return default_fade
    
    def fadeIn(self, fi, easefn="seio", fade_length=None, start=0):
        if ClipFlags.FadeIn in self.flags or fade_length:
            if fade_length:
                fade = fade_length
            else:
                fade = self.flags[ClipFlags.FadeIn]
            
            if start == 0:
                start_frame = self.start
            elif start == -1:
                start_frame = self.start - fade
            
            if fi < start_frame:
                return -1
            elif fi > start_frame + fade:
                return 1
            else:
                fv = (fi - start_frame) / fade
                a, _ = ease(easefn, fv)
                return a
        return -1
    
    def __repr__(self):
        return "<Clip:({:s}/{:04d}/{:04d}\"{:s}\")>".format([" -1", "NOW", " +1"][self.position+1], self.start, self.end, self.text)


class ClipGroupPens(DATPens):
    def __init__(self, clip_group):
        super().__init__()
        self.cg = clip_group
    
    def _iterate_tags(self, tag, pens):
        if hasattr(pens, "pens"):
            for pen in pens:
                if pen._tag == tag:
                    yield pen.data.get(tag), pen
                else:
                    yield from self._iterate_tags(tag, pen)
    
    def iterate_clips(self):
        yield from self._iterate_tags("clip", self)
    
    def iterate_slugs(self):
        yield from self._iterate_tags("slug", self)
    
    def iterate_lines(self):
        yield from self._iterate_tags("line", self)
    
    def map_clips(self, fn):
        for clip, pen in self.iterate_clips():
            fn(clip, pen)
        return self

    def remove_futures(self, clean=True):
        for clip, pen in self.iterate_clips():
            if clip.position > 0:
                pen.pens = []
        
        if clean:
            for _, pen in self.iterate_slugs():
                pen.pens = [p for p in pen.pens if len(p.pens) > 0]
            for line in self:
                line.pens = [p for p in line.pens if len(p.pens) > 0]
            self.pens = [p for p in self.pens if len(p.pens) > 0]
        
        return self
    
    def understroke(self, s=0, sw=5):
        for clip, pen in self.iterate_clips():
            pen.understroke(s=s, sw=sw)
        return self


class ClipGroup(Timeable):
    def __init__(self, timeline, index, clips):
        self.index = index
        self.clips = clips
        if len(clips) > 0:
            self.start = clips[0].start
            self.end = clips[-1].end
            self.track = clips[0].track
            self.valid = True
        else:
            self.start = 0
            self.end = 0
            self.track = None
            self.valid = False
        self.timeline = timeline
        self.style_indices = []

        for idx, clip in enumerate(clips):
            clip.idx = idx
            clip.group = self
    
    def styles(self):
        all_styles = set()
        for clip in self.clips:
            for style in clip.styles:
                all_styles.add(style)
        return all_styles
    
    def style_matching(self, style):
        for clip in self.clips:
            match = clip.style_matching(style)
            if match:
                return match
    
    def ldata(self, field, default):
        if len(self.clips) > 0:
            return self.clips[-1].inline_data.get(field, default)
    
    def current_style_matching(self, f:Frame, identifier:Union[str, Callable[[Clip], bool]]):
        for si in self.style_indices:
            sc = self.timeline.sequence[si].current(f.i)
            if sc and identifier(sc):
                if isinstance(identifier, str):
                    if identifier in sc.text:
                        return sc
                elif identifier(sc):
                    return sc
    
    def lines(self, ignore_newlines=False):
        lines = []
        line = []
        for clip in self.clips:
            if clip.type == ClipType.NewLine:
                if ignore_newlines:
                    if not clip.text.startswith(" "):
                        clip.text = " " + clip.text
                    line.append(clip)
                else:
                    lines.append(line)
                    line = [clip]
            elif clip.type == ClipType.GrafBreak:
                lines.append(line)
                cclip = copy.deepcopy(clip)
                cclip.text = "¶"
                lines.append([cclip])
                line = [clip]
                # add a graf mark
            else:
                line.append(clip)
        if len(line) > 0:
            lines.append(line)
        return lines
    
    def position(self, idx, styles):
        for clip in self.clips:
            clip.joined = False
        for clip in self.clips:
            clip:Clip
            clip.styles = []
            if False:
                if styles:
                    for style in styles:
                        if style:
                            for style_clip in style.clips:
                                if clip.start >= style_clip.start and clip.end <= style_clip.end:
                                    clip.styles.append(style_clip.ftext().strip())
                                elif style_clip.start >= clip.start and style_clip.end <= clip.end:
                                    clip.styles.append(style_clip.ftext().strip())
            if clip.start > idx:
                clip.position = 1
            elif clip.start <= idx and clip.end > idx:
                clip.position = 0
                before_clip = clip
                while before_clip.type == ClipType.JoinPrev:
                    before_clip = self.clips[before_clip.idx-1]
                    before_clip.joined = True
                try:
                    after_clip = self.clips[clip.idx+1]
                    while after_clip.type == ClipType.JoinPrev:
                        after_clip.joined = True
                        after_clip = self.clips[after_clip.idx+1]
                except IndexError:
                    pass
            else:
                clip.position = -1
            
            if True:
                for style in styles:
                    style:ClipTrack
                    if clip.position == -1:
                        sc = style.current(clip.end-1)
                    elif clip.position == 0:
                        sc = style.current(idx)
                    else:
                        sc = style.current(clip.start)
                    if sc:
                        clip.styles.extend([s.strip() for s in sc.ftext().strip().split(",")])
                        clip.style_clips.append(sc)
        return self
    
    def currentSyllable(self):
        for clip in self.clips:
            if clip.position == 0:
                return clip
    
    def currentWord(self):
        for clip in self.clips:
            if clip.position == 0:
                clips = [clip]
                before_clip = clip
                # walk back
                while before_clip.type == ClipType.JoinPrev:
                    before_clip = self.clips[before_clip.idx-1]
                    clips.insert(0, before_clip)
                # walk forward
                try:
                    after_clip = self.clips[clip.idx+1]
                    while after_clip.type == ClipType.JoinPrev:
                        clips.append(after_clip)
                        after_clip = self.clips[after_clip.idx+1]
                except IndexError:
                    pass
                return clips
    
    def currentLine(self):
        for line in self.lines():
            for clip in line:
                if clip.position == 0:
                    return line

    def sibling(self, clip, direction, wrap=False):
        try:
            if clip.idx + direction < 0 and not wrap:
                return None
            elif clip.idx + direction >= len(self.clips):
                if not wrap:
                    return None
                else:
                    return self.clips[0]
            return self.clips[clip.idx + direction]
        except IndexError:
            return None
    
    def text(self):
        txt = ""
        for c in self.clips:
            if c.type == ClipType.ClearScreen:
                pass
            elif c.type == ClipType.Isolated:
                txt += "( )"
            elif c.type == ClipType.JoinPrev:
                txt += "|"
            elif c.type == ClipType.NewLine:
                txt += "/(\\n)/"
            txt += c.text
        return txt
    
    def pens(self,
        f,
        render_clip_fn:Callable[[Frame, int, Clip, str], Tuple[str, Style]],
        rect=None,
        graf_style=GrafStyle(leading=20),
        fit=None,
        ignore_newlines=False,
        removeOverlap=False) -> ClipGroupPens:
        """
        render_clip_fn: frame, line index, clip, clip text — you must return a tuple of text to render and the Style to render it with
        """
        if not rect:
            rect = f.a.r
        group_pens = ClipGroupPens(self)
        lines = []
        groupings = []
        for idx, _line in enumerate(self.lines(ignore_newlines=ignore_newlines)):
            slugs = []
            texts = []
            for clip in _line:
                if clip.type == ClipType.Meta or clip.blank:
                    continue
                try:
                    ftext = clip.ftext()
                    text, style = render_clip_fn(f, idx, clip, ftext)
                    texts.append([text, clip.idx, style])
                except Exception as e:
                    print(e)
                    raise Exception("pens render_clip must return text & style")
            
            grouped_texts = []
            idx = 0
            done = False
            while not done:
                style = texts[idx][2]
                grouped_text = [texts[idx]]
                style_same = True
                while style_same:
                    idx += 1
                    try:
                        next_style = texts[idx][2]
                        if next_style == style:
                            style_same = True
                            grouped_text.append(texts[idx])
                        else:
                            style_same = False
                            grouped_texts.append(grouped_text)
                    except IndexError:
                        done = True
                        style_same = False
                        grouped_texts.append(grouped_text)
            
            for gt in grouped_texts:
                full_text = "".join([t[0] for t in gt])
                slugs.append(StyledString(full_text, gt[0][2]))
            groupings.append(grouped_texts)
            lines.append(slugs)
        
        lockups = []
        for line in lines:
            lockup = Lockup(line, preserveLetters=True, nestSlugs=True)
            if fit:
                lockup.fit(fit)
            lockups.append(lockup)
        graf = Graf(lockups, rect, graf_style)
        pens = graf.pens()#.align(rect, x="minx")
        
        re_grouped = DATPens()
        for idx, line in enumerate(lines):
            #print(pens, idx, line[0].text)
            line_dps = pens[idx]
            re_grouped_line = DATPens()
            re_grouped_line.tag("line")
            position = 1
            line_text = ""
            for gidx, gt in enumerate(groupings[idx]):
                group_dps = line_dps[gidx]
                tidx = 0
                last_clip_dps = None
                for (text, cidx, style) in gt:
                    clip:Clip = self.clips[cidx]
                    if clip.position == 0:
                        position = 0
                    elif clip.position == -1:
                        position = -1
                    line_text += clip.ftext()
                    clip_dps = DATPens(group_dps[tidx:tidx+len(text)])
                    clip_dps.tag("clip")
                    clip_dps.data["clip"] = self.clips[cidx]
                    clip_dps.data["line_index"] = idx
                    clip_dps.data["line"] = re_grouped_line
                    clip_dps.data["group"] = re_grouped
                    if clip.type == ClipType.JoinPrev and last_clip_dps:
                        grouped_clip_dps = last_clip_dps #DATPens()
                        #grouped_clip_dps.append(last_clip_dps)
                        #grouped_clip_dps.pens = last_clip_dps.pens
                        grouped_clip_dps.append(clip_dps)
                        #re_grouped_line[-1] = grouped_clip_dps
                        #last_clip_dps = grouped_clip_dps
                    else:
                        last_clip_dps = DATPens()
                        last_clip_dps.tag("slug")
                        last_clip_dps.append(clip_dps)
                        re_grouped_line.append(last_clip_dps)
                    tidx += len(text)
            re_grouped_line.data["line_index"] = idx
            re_grouped_line.data["position"] = position
            re_grouped_line.data["line_text"] = line_text
            re_grouped_line.addFrame(line_dps.getFrame())
            re_grouped.append(re_grouped_line)
        
        pens = re_grouped
        for pens in pens.pens:
            if removeOverlap:
                for pen in pens.pens:
                    pen.removeOverlap()
            group_pens.append(pens)
        
        for clip, pen in group_pens.iterate_clips():
            if clip.position == 1 or clip.text == "¶":
                #pen.f(0)
                pass
            if clip.blank:
                pen.pens = []
        
        for line in group_pens:
            line.reversePens() # line top-to-bottom
            for slug in line:
                slug.reversePens() # slugs left-to-right
                for clip in slug:
                    clip.reversePens() # glyphs left-to-right #.understroke(sw=5)
        
        group_pens.reversePens()
        return group_pens
    
    def iterate_clip_pens(self, pens):
        if hasattr(pens, "pens"):
            for pen in pens:
                if hasattr(pen, "data"):
                    if pen.data.get("clip"):
                        yield pen.data.get("clip"), pen
                    else:
                        yield from self.iterate_clip_pens(pen)

    def remove_futures(self, pens):
        for clip, pen in self.iterate_clip_pens(pens):
            if clip.position > 0:
                pen.pens = []
    
    def iterate_pens(self, pens, copy=True):
        for idx, line in enumerate(self.lines()):
            _pens = pens[idx]
            for cidx, clip in enumerate(line):
                if copy:
                    p = _pens.pens[cidx].copy()
                else:
                    p = _pens.pens[cidx]
                yield idx, clip, p
    
    def __repr__(self):
        return "<ClipGroup {:04d}-{:04d} \"{:s}\">".format(self.start, self.end, self.text())
    
    def __hash__(self):
        return self.text()


class ClipTrack():
    def __init__(self, sequence, clips, markers):
        self.sequence = sequence
        self.clips = clips
        self.markers = markers
        self.clip_groups = self.groupedClips(clips)
    
    def groupedClips(self, clips):
        groups = []
        group = []
        last_clip = None
        for idx, clip in enumerate(clips):
            if clip.type == ClipType.ClearScreen:
                if len(group) > 0:
                    groups.append(ClipGroup(self, len(groups), group))
                group = []
            elif clip.type == ClipType.JoinPrev:
                if last_clip:
                    last_clip.addJoin(clip, +1)
                    clip.addJoin(last_clip, -1)
            group.append(clip)
            last_clip = clip
        if len(group) > 0:
            groups.append(ClipGroup(self, len(groups), group))
        return groups
    
    def current(self, fi):
        for idx, clip in enumerate(self.clips):
            clip:Clip
            if clip.start <= fi and fi < clip.end:
                return clip
    
    def duration(self):
        duration = 0
        for c in self.clips:
            duration = max(duration, c.end)
        return duration
    
    def __repr__(self):
        return "<ClipTrack {:s}>".format("/".join([c.ftext() for c in self.clips[:3]]))


class Sequence(Timeline):
    def __init__(self, duration, fps, storyboard, tracks, workarea_track=0):
        self.workarea_track = workarea_track
        super().__init__(duration, fps, storyboard, tracks)
    
    def trackClipGroupForFrame(self, track_idx, frame_idx, styles=[], check_end=True):
        for gidx, group in enumerate(self[track_idx].clip_groups):
            group:ClipGroup
            group.style_indices = styles
            if not check_end:
                end_good = False
                try:
                    next_group = self[track_idx].clip_groups[gidx+1]
                    end_good = next_group.start > frame_idx
                except IndexError:
                    end_good = True
            if group.start <= frame_idx and ((check_end and group.end > frame_idx) or (not check_end and end_good)):
                if True:
                    style_tracks = [self[sidx] for sidx in styles]
                if False:
                    style_groups = None
                    if styles:
                        style_groups = []
                        for style in styles:
                            style_groups.append(self.trackClipGroupForFrame(style, frame_idx, check_end=False))
                return group.position(frame_idx, style_tracks)
    
    def clip_group(self, track_idx, f, styles=[]) -> ClipGroup:
        cg = self.trackClipGroupForFrame(track_idx, f.i if hasattr(f, "i") else f, styles)
        if cg:
            return cg
        else:
            return ClipGroup(self[track_idx], -1, [])
    
    def find_workarea(self):
        cg = self.trackClipGroupForFrame(self.workarea_track, self.cti)
        if cg:
            return [cg.start, cg.end]
    
    def jumps(self):
        js = self._jumps
        t = self[self.workarea_track]
        for clip in t.clips:
            js.insert(-1, clip.start)
        return js
    
    def text_for_frame(self, fi):
        cg = self.clip_group(self.workarea_track, fi)
        if cg and cg.currentSyllable():
            cgs = cg.currentSyllable()
            if cgs.start == fi:
                return cgs.input_text