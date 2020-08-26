from __future__ import print_function, absolute_import, division
from . import get_doxygen_root

# Need regular expressions to extract math labels
import re

# If flint is available, use it to help doxygen(XML).
try:
    import flint
except:
    pass

# added function
def flatten(xmlnode):
    # <xmlnode>this.text<child0>child0.text</child0>child0.tail...</xmlnode>

    t = ''

    # text of this node
    if xmlnode.text is not None:
        t += xmlnode.text

    # process all children recursively
    for n in xmlnode:
        t += ' '
        t += flatten(n)
        if n.tail is not None:
            t += ' '
            t += n.tail

    return t

def format_xml_paragraph(xmlnode,build_mode):
    """Format an Doxygen XML segment (principally a detaileddescription)
    as a paragraph for inclusion in the rst document

    Parameters
    ----------
    xmlnode

    Returns
    -------
    lines
        A list of lines.
    """
    return [l.rstrip() for l in
        _DoxygenXmlParagraphFormatter().generic_visit(xmlnode,build_mode=build_mode).lines]


class _DoxygenXmlParagraphFormatter(object):
    # This class follows the model of the stdlib's ast.NodeVisitor for tree traversal
    # where you dispatch on the element type to a different method for each node
    # during the traverse.

    # It's supposed to handle paragraphs, references, preformatted text (code blocks), and lists.

    def __init__(self):
        self.lines = ['']
        self.continue_line = False
        # We need to track specified math lables and place them prior to the ::math blocks
        self.math_labels = []
        self.build_mode = None

    # new
    def visit_latexonly(self, node):
        if self.build_mode != 'latexpdf':
            return

        # debug
        #import pdb; pdb.set_trace()

        # Just pass text through at this point
        #self.lines.append(node.text)

        # Convert \\ref{tag} to :ref:` ` and the sphinx latex processor
        # converts it to a proper label reference.
        text = node.text
        if text == None:
            return

        ref_match = re.search('\\\\ref{(.*?)}', text)
        #import pdb; pdb.set_trace()
        if ref_match is not None:
            tag_string = ref_match.groups()[0]
            #val = [' :ref:`%s`' % tag_string]
            val = [' :latex:`%s`' % text.strip()]
            self.lines[-1] += ''.join(val)

        return

    # new
    def visit_htmlonly(self, node):
        if self.build_mode != 'html':
            return

        text = node.text
        if text == None:
            return

        # Check for \eqref2{tag,txt} and convert to :ref:`tag`_
        eqref_match = re.search('\\\eqref2{(.*?)}', text)
        if eqref_match is not None:
            tag_string = eqref_match.groups()[0]
            if tag_string.find(',') >= 0:
                fc = tag_string.find(',')
                val = [' :math:numref:`%s` - %s' % (tag_string[0:fc],tag_string[fc+1:])]
            else:
                val = [' :math:numref:`%s`' % tag_string]
            self.lines[-1] += ''.join(val)

    # new
    # reStructured text only permits one label per math:: block
    def emit_math_labels(self):
        if len(self.math_labels) == 0:
            return

        print("[debug] inserting math labels")

        math_block_idx = -1
        for idx in range(len(self.lines)-1,0,-1):
            if self.lines[idx].startswith('.. math::'):
                math_block_idx = idx
                break

        # Add new label right after the math:: block
        if math_block_idx >=0:
            new_lines = self.lines[0:math_block_idx+1]
            new_label = "   :label: %s" % (self.math_labels[0])
            new_lines.append(new_label)
            new_lines.append('')
            new_lines = new_lines + self.lines[math_block_idx+1:]
            self.lines = new_lines

        #import pdb; pdb.set_trace()
        self.math_labels = []

    def visit(self, node):
        method = 'visit_' + node.tag
        print("[debug] method=%s" % (method))
        if len(self.math_labels) > 0 and node.tag != 'formula':
          self.emit_math_labels()
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node, build_mode=None):
        if build_mode:
            print("[debug] Setting build mode: %s" % (build_mode))
            self.build_mode = build_mode
        for child in node.getchildren():
            self.visit(child)
        return self

    # This is the original version with some debug
    # statements
    def visit_ref_angus(self, node):
    #def visit_ref(self, node):
        # find target node
        refid = node.get('refid')
        kind = None
        real_name = None
        name_node = None

        print("[debug] node.items():%s" % node.items())
        if node.get('kindref') == 'member':
            ref = get_doxygen_root().find('./compounddef/sectiondef/memberdef[@id="%s"]' % refid)
            # only set the kind if we find a function, otherwise it might be
            # a documentation reference
            if ref is not None:
                kind = 'func'
        elif node.get('kindref') == 'compound':
            ref = get_doxygen_root().find('./compounddef[@id="%s"]' % refid)
            if ref is not None:
                if ref.get('kind') == 'namespace':
                    kind = 'mod'
                elif ref.get('kind') == 'type':
                    kind = 'type'
        else:
            # we probably don't get here
            print('[debug] warning: slow ref search!')
            ref = get_doxygen_root().find('.//*[@id="%s"]' % refid)

        # get name of target
        if ref is not None:
            name_node = None

            if kind == 'func':
                name_node = ref.find('./name')
            elif kind == 'mod' or kind == 'type':
                name_node = ref.find('./compoundname')

            if name_node is not None:
                real_name = name_node.text.split('::')[-1]
            else:
                print("[debug] unimplemented link")
                self.lines[-1] += '(unimplemented link)' + node.text
                return
        else:
            # couldn't find link
            real_name = None

        if kind is None:
            # section link, we hope!
            val = ['`']
        else:
            print("[debug] :f:%s" % (kind))
            val = [':f:%s:`' % kind]

        val.append(node.text)
        if real_name is not None:
            val.extend((' <', real_name, '>`'))
        else:
            val.append('`')

        if kind is None:
            # convert into a proper link
            val.append('_')

        print("[debug] kind(%s) real_name(%s) name_node(%s) val(%s)" %
            (kind, real_name, name_node, val))
        self.lines[-1] += ''.join(val)

    # This was the modified original
    def visit_ref(self, node):
    #def visit_ref_modified(self, node):
        refid = node.get('refid')
        kind = None
        name_node = None
        ream_name = None

        # debug
        #if refid == 'General_Coordinate':
        #  import pdb; pdb.set_trace()
        ref = get_doxygen_root().findall('.//*[@id="%s"]' % refid)
        print("[debug] refid(%s) kindref(%s) kind(%s)" %
            (refid, node.get('kindref'), node.get('kind')))
        if ref:
            ref = ref[0]
            print("[debug] ref(%s)" % ref.items())
            if ref.tag == 'memberdef':
                parent = ref.xpath('./ancestor::compounddef/compoundname')[0].text
                name = ref.find('./name').text
                real_name = parent + '::' + name
            elif ref.tag in ('compounddef', 'enumvalue'):
                if ref.get('kind') == 'page':
                    # :ref: works, but requires an explicit tag placed at the top of pages
                    # that generates an INFO message.  FIX LATER.
                    val = [':ref:`%s`' % ref.get('id')]
                    #val = ['`%s`_' % refid]
                    self.lines[-1] += ''.join(val)
                    return
                name_node = ref.find('./name')
                real_name = name_node.text if name_node is not None else ''
            elif ref.tag in ('anchor','sect1','sect2'):
                # If _1CITEREF_ this is a doxygen processed citation
                if refid.find('_1CITEREF_') >= 0:
                    citation = refid[18:]
                    val = [':cite:`%s`' % (citation)]
                    self.lines[-1] += ''.join(val)
                    return
                # Treat the rest of these as general links
                if refid.find('_1') >= 0:
                    val = [':ref:`%s`' % refid]
                    #val = ['`%s`_' % refid]
                    self.lines[-1] += ''.join(val)
                    return
                else:
                    print('[error] Unimplemented anchor tag: %s' % (ref.tag))
                    raise NotImplementedError(ref.tag)
            else:
                print('[error] Unimplemented tag: %s' % (ref.tag))
                import pdb; pdb.set_trace()
                raise NotImplementedError(ref.tag)
        else:
            real_name = None

        #debug
        #import pdb; pdb.set_trace()
        val = [':cpp:any:`', node.text]
        if real_name:
            val.extend((' <', real_name, '>`'))
        else:
            val.append('`')
        if node.tail is not None:
            val.append(node.tail)

        print("[debug] kind(%s) real_name(%s) node_name(%s)" %
            (kind, real_name, name_node))
        self.lines[-1] += ''.join(val)

    # add visit_ulink
    def visit_ulink(self, node):
        self.para_text('`%s <%s>`_' % (node.text, node.get('url')))

    # add visit_emphasis
    def visit_emphasis(self, node):
        self.para_text('*%s*' % node.text)

    # add role_text
    def role_text(self, node, role):
        # XXX we should probably escape preceeding whitespace...
        # but there's no backward equivalent of `tail`
        text = ' :%s:`%s`' % (role, node.text)

        if node.tail is not None and not node.tail.startswith(' '):
            # escape following whitespace
            text += '\\'

        text += ' ' # interpretered text needs surrounding whitespace
        self.para_text(text)

    # add visit_image
    def visit_image(self, node):
        if len(node.text.strip()):
            type = 'figure'
        else:
            type = 'image'

        self.lines.append('.. %s:: /images/%s' % (type, node.get('name')))

        if type == 'figure':
            self.lines.extend(['', node.text])

    # add visit_superscript
    def visit_superscript(self, node):
        self.role_text(node, 'superscript')

    # add visit_subscript
    def visit_subscript(self, node):
        self.role_text(node, 'subscript')

    # add para_text parser
    def para_text(self, text):
        if text is not None:
            if self.continue_line:
                self.lines[-1] += text
            else:
                self.lines.append(text.lstrip())

    def visit_para(self, node):
        self.para_text(node.text)

        # visit children and append tail
        for child in node.getchildren():
            self.visit(child)
            self.para_text(child.tail)
            self.continue_line = True

        # replaced
        #if node.text is not None:
        #    if self.continue_line:
        #        self.lines[-1] += node.text
        #    else:
        #        self.lines.append(node.text)
        #self.generic_visit(node)
        self.lines.append('')
        self.continue_line = False

    # add visit_formula
    def visit_formula(self, node):
        text = node.text.strip()

        # Remove the faked link for the html version
        if self.build_mode == 'latexpdf':
            label_match = re.search(' \\\\label{(html:.*?)}.*?\\\\\\\\', text)
            if label_match:
                replace_string = label_match.group()
                text = text.replace(replace_string,'')

        # detect inline or block math
        if text.startswith('\\[') or not text.startswith('$'):
            if text.startswith('\\['):
                text = text[2:-2]

            # if we are emitting a math block and we have
            # pending math labels, go back and emit those
            # first.
            if len(self.math_labels) > 0:
                self.emit_math_labels()

            self.lines.append('')
            self.lines.append('.. math:: ' + text)
            self.lines.append('')
            self.continue_line = False
        else:
            inline = ':math:`' + node.text.strip()[1:-1].strip() + '`'
            if self.continue_line:
                self.lines[-1] += inline
            else:
                self.lines.append(inline)

            self.continue_line = True

        # detect \label{html:tag} blocks
        if text.find('\\label') >= 0:
            label_matches = re.findall('\\\label{html:(.*?)} ',text)
            if len(label_matches) > 0:
                [self.math_labels.append(i) for i in label_matches]

    def visit_parametername(self, node):
        if 'direction' in node.attrib:
            direction = '[%s] ' % node.get('direction')
        else:
            direction = ''

        # replace
        #self.lines.append('**%s** -- %s' % (
        #    node.text, direction))
        self.lines.append(':param %s: %s' % (node.text, direction))
        self.continue_line = True

    def visit_parameterlist(self, node):
        lines = [l for l in type(self)().generic_visit(node).lines if l is not '']
        # replaced
        #self.lines.extend([':parameters:', ''] + ['* %s' % l for l in lines] + [''])
        self.lines.extend([''] + lines + [''])

    # Doxygen generates a simplesect for functions with
    # a specified return argument.  For now, we leave a :returns:
    # marker so we can fix up the document using flint.
    def visit_simplesect(self, node):
        #import pdb; pdb.set_trace()
        if node.get('kind') == 'return':
            self.lines.append(':returns undefined: ')
            self.continue_line = True
        self.generic_visit(node)

    # add

    def visit_sect(self, node, char):
        """Generic visit section"""
        title_node = node.find('title')
        if title_node is not None:
            title = title_node.text
            self.lines.append(title)
            self.lines.append(len(title) * char)
            self.lines.append('')

        self.generic_visit(node)

    def visit_sect1(self, node):
        self.visit_sect(node, '=')

    def visit_sect2(self, node):
        self.visit_sect(node, '-')

    def visit_sect3(self, node):
        self.visit_sect(node, '^')

    def visit_sect4(self, node):
        self.visit_sect(node, '"')

    # add end

    def visit_listitem(self, node):
        char = '*' if node.getparent().tag == 'itemizedlist' else '#'
        self.lines.append('')
        self.lines.append(char + ' ')
        # replaced
        #self.lines.append('   - ')
        self.continue_line = True
        self.generic_visit(node)

    # add
    def preformat_text(self, lines):
        self.lines.extend(('::', ''))
        self.lines.extend(['  ' + l for l in lines])
        self.lines.append('')

    def visit_preformatted(self, node):
        segment = [node.text if node.text is not None else '']
        for n in node.getchildren():
            segment.append(n.text)
            if n.tail is not None:
                segment.append(n.tail)

        lines = ''.join(segment).split('\n')
        # add line
        self.preformat_text(lines)
        # extra? no effect
        #self.lines.extend(('.. code-block:: C++', ''))
        #self.lines.extend(['  ' + l for l in lines])

    # add 
    def visit_programlisting(self, node):
        lines = []
        for n in node.getchildren():
            lines.append(flatten(n))
        self.preformat_text(lines)

    #add
    def visit_verbatim(self, node):
        self.visit_preformatted(node)

    def visit_computeroutput(self, node):
        c = node.find('preformatted')
        if c is not None:
            return self.visit_preformatted(c)
        # add
        # I don't think we can put links inside
        # computeroutput text...
        self.lines[-1] += '``' + flatten(node) + '``'
        # omitted
        #return self.visit_preformatted(node)

    def visit_xrefsect(self, node):
        if node.find('xreftitle').text == 'Deprecated':
            sublines = type(self)().generic_visit(node).lines
            self.lines.extend(['.. admonition:: Deprecated'] + ['   ' + s for s in sublines])
            return
        # add - if not depricated
        title = node.find('xreftitle').text
        sublines = type(self)().generic_visit(node).lines
        self.lines.extend(['.. admonition:: %s' % title] + ['   ' + s for s in sublines])
        #else:
        #    raise ValueError(node)

    def visit_subscript(self, node):
        self.lines[-1] += '\ :sub:`%s` %s' % (node.text, node.tail)

    def visit_table(self, node):
        # save the number of columns
        cols = int(node.get('cols'))
        table = []
        # save the current output
        lines = self.lines

        # get width of each column
        widths = [0] * cols

        # build up the table contents
        for row_node in node.findall('row'):
            row = []
            for i, entry in enumerate(row_node.getchildren()):
                self.lines = ['']
                self.generic_visit(entry)
                row.append(self.lines)

                # find width of this entry (including leading and trailing space)
                widths[i] = max(widths[i], max([len(line) for line in self.lines]) + 2)

            table.append(row)

        def append_row(row):
            # find number of lines in row
            num_lines = max([len(e) for e in row])
            lines = []

            for k in range(num_lines):
                line = '|'
                for i, e in enumerate(row):
                    if k < len(e):
                        # this is a valid line
                        line += ' ' + e[k]
                        # pad rest of line
                        line += ' ' * (widths[i] - len(e[k]) - 1)
                    else:
                        # invalid line, just fill with spaces
                        line += ' ' * widths[i]

                    line += '|'

                lines.append(line)

            return lines

        self.lines = lines
        # start with a blank
        self.lines.append('')

        # usual separator line
        sep = '+'
        for width in widths:
            sep += '-' * width
            sep += '+'

        self.lines.append(sep)

        # header row
        self.lines.extend(append_row(table[0]))
        # header separator uses '=' instead of '-'
        self.lines.append(sep.replace('-', '='))

        # loop over body rows
        for row in table[1:]:
            self.lines.extend(append_row(row))
            self.lines.append(sep)

        # end with a blank
        self.lines.append('')
