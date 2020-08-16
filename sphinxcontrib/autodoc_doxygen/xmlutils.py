from __future__ import print_function, absolute_import, division
from . import get_doxygen_root

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

def format_xml_paragraph(xmlnode):
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
    return [l.rstrip() for l in _DoxygenXmlParagraphFormatter().generic_visit(xmlnode).lines]


class _DoxygenXmlParagraphFormatter(object):
    # This class follows the model of the stdlib's ast.NodeVisitor for tree traversal
    # where you dispatch on the element type to a different method for each node
    # during the traverse.

    # It's supposed to handle paragraphs, references, preformatted text (code blocks), and lists.

    def __init__(self):
        self.lines = ['']
        self.continue_line = False

    def visit(self, node):
        method = 'visit_' + node.tag
        print("[debug] method=%s" % (method))
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        for child in node.getchildren():
            self.visit(child)
        return self

    def visit_ref(self, node):
        print("[debug] node.items()=",node.items())
        refid = node.get('refid')
        ref = get_doxygen_root().findall('.//*[@id="%s"]' % refid)
        if ref:
            ref = ref[0]
            if ref.tag == 'memberdef':
                parent = ref.xpath('./ancestor::compounddef/compoundname')[0].text
                name = ref.find('./name').text
                real_name = parent + '::' + name
            elif ref.tag in ('compounddef', 'enumvalue'):
                name_node = ref.find('./name')
                real_name = name_node.text if name_node is not None else ''
            elif ref.tag in ('anchor'):
                # If _1CITEREF_ this is a doxygen processed citation
                if refid.find('_1CITEREF_') >= 0:
                    citation = refid[18:]
                    val = [':cite:`%s`' % (citation)]
                    self.lines[-1] += ' '.join(val)
                    return
                # Treat the rest of these as general links
                if refid.find('_1') >= 0:
                    val = [':ref:`%s`' % refid]
                    self.lines[-1] += ' '.join(val)
                    return
                else:
                    print('[error] Unimplemented anchor tag: %s' % (ref.tag))
                    raise NotImplementedError(ref.tag)
            else:
                print('[error] Unimplemented tag: %s' % (ref.tag))
                raise NotImplementedError(ref.tag)
        else:
            real_name = None

        val = [':cpp:any:`', node.text]
        if real_name:
            val.extend((' <', real_name, '>`'))
        else:
            val.append('`')
        if node.tail is not None:
            val.append(node.tail)

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

        # detect inline or block math
        if text.startswith('\\[') or not text.startswith('$'):
            if text.startswith('\\['):
                text = text[2:-2]

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
        # Fix python warning
        lines = [l for l in type(self)().generic_visit(node).lines if l != '']
        # replaced
        #self.lines.extend([':parameters:', ''] + ['* %s' % l for l in lines] + [''])
        self.lines.extend([''] + lines + [''])

    def visit_simplesect(self, node):
        if node.get('kind') == 'return':
            self.lines.append(':returns: ')
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
        self.lines.extend(('.. code-block:: C++', ''))
        self.lines.extend(['  ' + l for l in lines])

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
        return self.visit_preformatted(node)

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
