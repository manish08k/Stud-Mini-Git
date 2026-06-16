BASH_COMPLETION = '''
_stud_completion() {
    local cur prev words cword
    _init_completion || return
    local commands="init add commit status log branch checkout merge diff push pull install publish run audit ai help"
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=($(compgen -W "$commands" -- "$cur"))
    else
        case "${words[1]}" in
            checkout|branch|merge)
                local branches
                branches=$(stud branch --list 2>/dev/null | tr -d '* ')
                COMPREPLY=($(compgen -W "$branches" -- "$cur"))
                ;;
            add)
                COMPREPLY=($(compgen -f -- "$cur"))
                ;;
            run)
                local workflows
                workflows=$(ls .stud/workflows/*.yml 2>/dev/null | xargs -I{} basename {} .yml)
                COMPREPLY=($(compgen -W "$workflows" -- "$cur"))
                ;;
        esac
    fi
}
complete -F _stud_completion stud
'''

ZSH_COMPLETION = '''
#compdef stud
_stud() {
    local -a commands
    commands=(
        'init:Initialize a new Stud repository'
        'add:Stage files'
        'commit:Create a commit'
        'status:Show working tree status'
        'log:Show commit history'
        'branch:Manage branches'
        'checkout:Switch branches or restore files'
        'merge:Merge branches'
        'diff:Show changes'
        'push:Push to remote'
        'pull:Pull from remote'
        'install:Install dependencies'
        'publish:Publish package'
        'run:Run a workflow'
        'audit:Run security audit'
        'ai:AI-powered commands'
        'help:Show help'
    )
    _describe 'stud command' commands
}
_stud "$@"
'''

FISH_COMPLETION = '''
set -l commands init add commit status log branch checkout merge diff push pull install publish run audit ai help

complete -c stud -f -n "not __fish_seen_subcommand_from $commands" -a "$commands"
complete -c stud -n "__fish_seen_subcommand_from checkout branch merge" -a "(stud branch --list 2>/dev/null)"
complete -c stud -n "__fish_seen_subcommand_from add" -a "(ls)"
'''


def get_completion_script(shell: str) -> str:
    shells = {
        "bash": BASH_COMPLETION,
        "zsh": ZSH_COMPLETION,
        "fish": FISH_COMPLETION,
    }
    script = shells.get(shell)
    if script is None:
        raise ValueError(f"unsupported shell: {shell!r}. Supported: bash, zsh, fish")
    return script.strip()


def install_instructions(shell: str) -> str:
    if shell == "bash":
        return 'Add to ~/.bashrc:\n  eval "$(stud completion bash)"'
    if shell == "zsh":
        return 'Add to ~/.zshrc:\n  eval "$(stud completion zsh)"'
    if shell == "fish":
        return "Run:\n  stud completion fish > ~/.config/fish/completions/stud.fish"
    return f"No install instructions for shell: {shell}"
