#!/usr/bin/perl
#
########################################################
#
# oracle_listeners.pl
#
# Checkmk agent plugin for Oracle listener monitoring.
# Monitors standard Oracle listeners and Oracle RAC SCAN
# / management listeners. Self-contained: all functions
# inlined, no library deps.
#
# Based on: oramp_lsnrchk.pl (NiCE IT Management Solutions)
#
# Metrics collected:
#   3000 - Standard Oracle listener   (lsnrctl status)
#   3010 - Oracle RAC SCAN listener   (srvctl status scan_listener)
#   3020 - Oracle Management listener (srvctl status mgmtlsnr)
#
# Output format (sep=124 i.e. pipe):
#   <<<oracle_listeners:sep(124)>>>
#   OBJECT|METRIC|VALUE|OPTION1|OPTION2|OPTION3|OPTION4|OPTION5
#
########################################################

use strict;
use warnings;

our $PROGRAMNAME = "oracle_listeners.pl";

##################################################################
# Platform helpers
##################################################################

sub is_windows { return ( $^O eq "MSWin32" ) ? 1 : 0; }
sub is_unix    { return ( $^O =~ /hpux|linux|aix|solaris/ ) ? 1 : 0; }

##################################################################
# Utility functions (inlined from oramp_genlib)
##################################################################

sub trim
{
    my @out = @_;
    for (@out)
    {
        if ( defined $_ )
        {
            s/^\s+//;
            s/\s+$//;
        }
    }
    return wantarray ? @out : $out[0];
}

sub make_ospath
{
    my $path = $_[0];
    return "" unless defined $path;
    chomp $path;
    $path =~ s/"//g;
    if ( is_windows() )
    {
        $path =~ s/\//\\/g;
        $path =~ s/\\{2,}/\\/g;
    }
    else
    {
        $path =~ s/\/{2,}/\//g;
    }
    return $path;
}

# Replace pipe characters so they cannot break the field structure.
sub sanitise_option
{
    my $s = defined $_[0] ? $_[0] : "";
    $s =~ s/\|/?/g;
    return $s;
}

sub truncate_str
{
    my ( $s, $max ) = @_;
    $max //= 512;
    if ( length($s) > $max )
    {
        $s = substr( $s, 0, $max - 4 ) . " ...";
    }
    return $s;
}

sub get_shorthostname
{
    my $host = $ENV{HOSTNAME} || $ENV{COMPUTERNAME} || "";
    unless ($host)
    {
        chomp( $host = `hostname 2>/dev/null` );
    }
    $host =~ s/\..*$//;    # strip domain suffix
    return $host;
}

my $HOSTNAME = get_shorthostname();

##################################################################
# Oracle home discovery
##################################################################

sub read_oratab
{
    my $oratab = "";
    for my $candidate ( "/etc/oratab", "/var/opt/oracle/oratab" )
    {
        if ( -r $candidate )
        {
            $oratab = $candidate;
            last;
        }
    }
    my @entries;
    return @entries unless $oratab;

    open( my $fh, "<", $oratab ) or return @entries;
    while (<$fh>)
    {
        chomp;
        s/^\s+//;
        s/#.*//;
        s/\s+$//;
        next unless length;
        my ( $sid, $home ) = split( /:/, $_, 3 );
        next unless defined $sid && defined $home;
        $sid  = trim($sid);
        $home = trim($home);
        next unless length($home) && $home ne "N";
        push @entries, { SID => $sid, ORAHOME => $home };
    }
    close($fh);
    return @entries;
}

# Collect unique candidate home paths from oratab, environment, and (Windows) registry.
sub _home_candidates
{
    my @raw;

    # oratab (Unix and some Windows installs)
    for my $e ( read_oratab() )
    {
        push @raw, $e->{ORAHOME};
    }

    # Windows registry
    if ( is_windows() )
    {
        for my $hive (
            'HKEY_LOCAL_MACHINE\\SOFTWARE\\ORACLE',
            'HKEY_LOCAL_MACHINE\\SOFTWARE\\WOW6432Node\\ORACLE'
          )
        {
            open( my $reg, "reg query \"$hive\" /s /v ORACLE_HOME 2>nul |" ) or next;
            while (<$reg>)
            {
                chomp;
                push @raw, trim($1) if /ORACLE_HOME\s+REG_SZ\s+(.*)/i;
            }
            close($reg);
        }
    }

    # Environment variables
    push @raw, $ENV{ORACLE_HOME} if $ENV{ORACLE_HOME};
    push @raw, $ENV{GRID_HOME}   if $ENV{GRID_HOME};

    return @raw;
}

# Return unique Oracle homes that have lsnrctl present.
sub find_oracle_homes
{
    my %seen;
    my @homes;
    for my $home ( _home_candidates() )
    {
        next unless defined $home && length $home;
        $home = trim($home);
        next if $seen{$home}++;
        my $lsnrctl = make_ospath( $home . "/bin/lsnrctl" . ( is_windows() ? ".exe" : "" ) );
        push @homes, $home if -e $lsnrctl;
    }
    return @homes;
}

# Return unique Grid/RAC homes that have srvctl present.
sub find_grid_homes
{
    my %seen;
    my @homes;
    for my $home ( _home_candidates() )
    {
        next unless defined $home && length $home;
        $home = trim($home);
        next if $seen{$home}++;
        my $srvctl = make_ospath( $home . "/bin/srvctl" . ( is_windows() ? ".exe" : "" ) );
        push @homes, $home if -e $srvctl;
    }
    return @homes;
}

##################################################################
# Listener name discovery via running processes
# Returns list of { NAME => $name, ORAHOME => $orahome }
##################################################################

sub scan_listener_processes
{
    my @listeners;
    my %seen;

    if ( is_windows() )
    {
        # Enumerate Oracle TNS listener Windows services.
        # Service name format: OracleOra<homeid>TNSListener[<name>]
        open( my $sc, 'sc query state= all 2>nul |' ) or return @listeners;
        my @svc_names;
        while (<$sc>)
        {
            chomp;
            push @svc_names, trim($1) if /SERVICE_NAME:\s*(Oracle\S*TNSListener\S*)/i;
        }
        close($sc);

        for my $svcname (@svc_names)
        {
            my ($suffix) = ( $svcname =~ /TNSListener(.*)/i );
            my $name = ( defined $suffix && $suffix ne "" ) ? uc( trim($suffix) ) : "LISTENER";

            # Resolve oracle home from service binary path
            my $orahome = "";
            open( my $qc, "sc qc \"$svcname\" 2>nul |" ) or next;
            while (<$qc>)
            {
                chomp;
                if (/BINARY_PATH_NAME\s*:\s*(.*)/i)
                {
                    my $bin = trim($1);
                    ( $orahome = $bin ) =~ s/[\\\/]bin[\\\/]tnslsnr.*$//i;
                    last;
                }
            }
            close($qc);

            my $key = lc("$name:$orahome");
            next if $seen{$key}++;
            push @listeners, { NAME => $name, ORAHOME => $orahome };
        }
    }
    else
    {
        # Unix: scan tnslsnr processes.
        # Typical process line: /oracle/home/bin/tnslsnr LSNRNAME -inherit
        open( my $ps, "ps -ef 2>/dev/null |" ) or return @listeners;
        while (<$ps>)
        {
            chomp;
            if ( m{(\S+/bin/tnslsnr)\s+(\S+)}i )
            {
                my ( $bin, $name ) = ( $1, $2 );
                next if $name =~ /^-/;    # skip flags
                ( my $orahome = $bin ) =~ s{/bin/tnslsnr$}{}i;
                my $key = lc("$name:$orahome");
                next if $seen{$key}++;
                push @listeners, { NAME => uc($name), ORAHOME => $orahome };
            }
        }
        close($ps);
    }

    return @listeners;
}

##################################################################
# Listener name discovery via listener.ora
# Parses $ORACLE_HOME/network/admin/listener.ora (and fallback
# locations) to find all *configured* listener names, including
# those whose process is currently stopped.
# Returns a list of uppercase listener names.
##################################################################

sub find_listeners_from_listener_ora
{
    my ($orahome) = @_;
    my @names;
    my %seen;

    # Search order: home-specific path first, then TNS_ADMIN, then /etc (Unix)
    my @search_paths = ( make_ospath( $orahome . "/network/admin/listener.ora" ) );
    push @search_paths, make_ospath( $ENV{TNS_ADMIN} . "/listener.ora" ) if $ENV{TNS_ADMIN};
    push @search_paths, "/etc/listener.ora" unless is_windows();

    # Top-level parameters in listener.ora that are NOT listener definitions
    my $skip_re = qr/^(
        SID_LIST_                       |
        ADR_BASE_                       |
        DIAG_ADR_ENABLED_               |
        INBOUND_CONNECT_TIMEOUT_        |
        CONNECT_TIMEOUT_                |
        LOGGING_                        |
        LOG_FILE_                       |
        LOG_DIRECTORY_                  |
        TRACE_LEVEL_                    |
        TRACE_FILE_                     |
        TRACE_DIRECTORY_                |
        TRACE_TIMESTAMP_                |
        RECEIVE_BUF_SIZE                |
        SEND_BUF_SIZE                   |
        SSL_                            |
        WALLET_                         |
        DEFAULT_SERVICE_                |
        PASSWORDS_                      |
        ADMIN_RESTRICTIONS_             |
        SECURE_REGISTER_                |
        SECURE_PROTOCOL_                |
        SECURE_CONTROL_                 |
        SUBSCRIBE_FOR_NODE_DOWN_EVENT_  |
        DYNAMIC_REGISTRATION_
    )/xi;

    for my $fname (@search_paths)
    {
        next unless -r $fname;
        open( my $fh, "<", $fname ) or next;
        while (<$fh>)
        {
            chomp;
            s/#.*//;    # strip inline comments
            # Top-level stanza: identifier at column 0 followed by optional
            # whitespace then '='.  Dots are excluded so NAMES.DIRECTORY_PATH
            # is never captured as a listener name.
            if (/^([A-Za-z][A-Za-z0-9_]*)\s*=/)
            {
                my $id = uc( trim($1) );
                next if $id =~ $skip_re;
                next if $seen{$id}++;
                push @names, $id;
            }
        }
        close($fh);
        last;    # use the first readable listener.ora found
    }

    return @names;
}

##################################################################
# Exclusion configuration (Checkmk Agent Bakery)
#
# Config file: $MK_CONFDIR/oracle_listeners.cfg
#   MK_CONFDIR is set by check_mk_agent (typically /etc/check_mk on Linux,
#   C:\ProgramData\checkmk\agent\config on Windows). Falls back to those
#   conventional paths when the plugin is run manually outside the agent.
#
# Supported directives:
#   EXCLUDE = <LSNRNAME>             # exclude by name across all homes
#   EXCLUDE = <LSNRNAME>:<ORAHOME>  # exclude by name + specific home
##################################################################

sub read_plugin_config
{
    # MK_CONFDIR is set by check_mk_agent before invoking plugins.
    # Fall back to the conventional path when run manually.
    my $default_confdir = is_windows()
        ? 'C:\ProgramData\checkmk\agent\config'
        : '/etc/check_mk';
    my $confdir  = $ENV{MK_CONFDIR} || $default_confdir;
    my $cfg_file = make_ospath( $confdir . '/oracle_listeners.cfg' );

    my %config = ( EXCLUDE => [] );
    return %config unless -r $cfg_file;

    open( my $fh, "<", $cfg_file ) or return %config;
    while (<$fh>)
    {
        chomp;
        s/#.*//;
        s/^\s+//;
        s/\s+$//;
        next unless length;

        if (/^EXCLUDE\s*=\s*(.+)$/i)
        {
            push @{ $config{EXCLUDE} }, uc( trim($1) );
        }
    }
    close($fh);
    return %config;
}

# Returns 1 if the listener matches any exclusion pattern.
# Matches name-only ("MYLISTENER") or name+home ("MYLISTENER:/path/to/home").
sub is_excluded
{
    my ( $name, $orahome, $excludes ) = @_;
    $name    = uc( $name    // "" );
    $orahome = uc( $orahome // "" );

    for my $pattern (@$excludes)
    {
        return 1 if $pattern eq $name;
        return 1 if $pattern eq "$name:$orahome";
    }
    return 0;
}

##################################################################
# Command execution
##################################################################

sub run_cmd
{
    my ( $cmd, $options ) = @_;
    $options //= "";
    my @output;
    unless ( -e $cmd )
    {
        warn "$PROGRAMNAME: not found: '$cmd'\n";
        return undef;
    }
    if ( open( my $pipe, "$cmd $options |" ) )
    {
        while (<$pipe>)
        {
            chomp;
            push @output, $_;
        }
        close($pipe);
    }
    else
    {
        warn "$PROGRAMNAME: failed to run '$cmd $options': $!\n";
        return undef;
    }
    return \@output;
}

##################################################################
# Metric 3000 - Standard Oracle listener
# lsnrctl status <name>
# Value: 0 = running OK, 1 = error / not running
##################################################################

sub metric3000
{
    my ( $orahome, $lsnrname ) = @_;

    local $ENV{ORACLE_HOME} = $orahome;

    my $lsnrctl = make_ospath( $orahome . "/bin/lsnrctl" . ( is_windows() ? ".exe" : "" ) );
    my $output  = run_cmd( $lsnrctl, "status " . $lsnrname );

    my ( $res, $error ) = ( 0, "" );

    if ( defined $output )
    {
        for (@$output)
        {
            if (/^\s*(TNS-\d+\S*.*?)$/)
            {
                $error = trim($1);
                $res   = 1;
                last;
            }
        }
    }
    else
    {
        $res   = 1;
        $error = "lsnrctl command failed";
    }

    return {
        OBJECT  => sanitise_option("$lsnrname:$orahome"),
        NUMBER  => 3000,
        VALUE   => $res,
        OPTION1 => "LSNRNAME=" . sanitise_option($lsnrname),
        OPTION2 => "ORAHOME="  . sanitise_option($orahome),
        OPTION3 => "ERROR="    . truncate_str( sanitise_option( $error || "No error" ) ),
        OPTION4 => "NODE=$HOSTNAME",
    };
}

##################################################################
# Metric 3010 - Oracle RAC SCAN listeners
# srvctl status scan_listener
# Returns a list of hashrefs, one per SCAN listener found.
# Value: 0 = running, 1 = not running
##################################################################

sub metric3010
{
    my ($orahome) = @_;

    my $srvctl = make_ospath( $orahome . "/bin/srvctl" . ( is_windows() ? ".exe" : "" ) );
    my $output = run_cmd( $srvctl, "status scan_listener" );
    my @results;

    unless ( defined $output )
    {
        push @results, {
            OBJECT  => "SCAN_LISTENER:" . sanitise_option($orahome),
            NUMBER  => 3010,
            VALUE   => 1,
            OPTION1 => "LSNRNAME=SCAN_LISTENER",
            OPTION2 => "ORAHOME=" . sanitise_option($orahome),
            OPTION3 => "ERROR=srvctl command failed",
            OPTION4 => "NODE=",
        };
        return @results;
    }

    my %parsed;
    for (@$output)
    {
        # "SCAN listener LISTENER_SCAN1 is running on node rac1"
        if (/^SCAN listener (\S+) is running on node\s+(.*)/i)
        {
            my ( $name, $node ) = ( uc( trim($1) ), trim($2) );
            $parsed{$name}{running} = 1;
            $parsed{$name}{node}    = $node;
        }
        # "SCAN listener LISTENER_SCAN1 is not running"
        elsif (/^SCAN listener (\S+) is not running/i)
        {
            my $name = uc( trim($1) );
            $parsed{$name}{running} //= 0;
            $parsed{$name}{node}    //= "";
        }
    }

    for my $name ( sort keys %parsed )
    {
        my $info    = $parsed{$name};
        my $running = $info->{running} // 0;
        push @results, {
            OBJECT  => sanitise_option("$name:$orahome"),
            NUMBER  => 3010,
            VALUE   => $running ? 0 : 1,
            OPTION1 => "LSNRNAME=$name",
            OPTION2 => "ORAHOME=" . sanitise_option($orahome),
            OPTION3 => "ERROR=" . ( $running ? "No error" : "SCAN listener not running" ),
            OPTION4 => "NODE=" . sanitise_option( $info->{node} // "" ),
        };
    }

    return @results;
}

##################################################################
# Metric 3020 - Oracle Management listener (Oracle 12c+ Grid)
# srvctl status mgmtlsnr
# Value: 0 = running, 1 = not running
# Returns undef when mgmtlsnr is not configured.
##################################################################

sub metric3020
{
    my ($orahome) = @_;

    my $srvctl = make_ospath( $orahome . "/bin/srvctl" . ( is_windows() ? ".exe" : "" ) );
    my $output = run_cmd( $srvctl, "status mgmtlsnr" );

    unless ( defined $output )
    {
        return {
            OBJECT  => "MGMTLSNR:" . sanitise_option($orahome),
            NUMBER  => 3020,
            VALUE   => 1,
            OPTION1 => "LSNRNAME=MGMTLSNR",
            OPTION2 => "ORAHOME=" . sanitise_option($orahome),
            OPTION3 => "ERROR=srvctl command failed",
            OPTION4 => "NODE=",
        };
    }

    my ( $res, $error, $node ) = ( 0, "", "" );
    my $found = 0;

    for (@$output)
    {
        # "Listener MGMTLSNR is running on node: rac1" (colon form)
        # "Listener MGMTLSNR is running on rac1"       (space form)
        if (/^Listener \S+ is running on.*?[:\s]([\w][\w,\s]*)$/i)
        {
            $node  = trim($1);
            $res   = 0;
            $found = 1;
            last;
        }
        elsif (/^Listener \S+ is not running/i)
        {
            $res   = 1;
            $error = trim($_);
            $found = 1;
            last;
        }
    }

    return undef unless $found;    # mgmtlsnr not configured

    return {
        OBJECT  => "MGMTLSNR:" . sanitise_option($orahome),
        NUMBER  => 3020,
        VALUE   => $res,
        OPTION1 => "LSNRNAME=MGMTLSNR",
        OPTION2 => "ORAHOME=" . sanitise_option($orahome),
        OPTION3 => "ERROR=" . sanitise_option( $error || "No error" ),
        OPTION4 => "NODE=" . sanitise_option($node),
    };
}

##################################################################
# Output formatting (same structure as oracle_rac_services.pl)
##################################################################

sub format_output_line
{
    my $r = $_[0];
    return $r->{OBJECT} . "|"
        . $r->{NUMBER}  . "|"
        . $r->{VALUE}   . "|"
        . ( $r->{OPTION1} // "None" ) . "|"
        . ( $r->{OPTION2} // "None" ) . "|"
        . ( $r->{OPTION3} // "None" ) . "|"
        . ( $r->{OPTION4} // "None" ) . "|"
        . ( $r->{OPTION5} // "None" ) . "\n";
}

##################################################################
# MAIN
##################################################################

$ENV{SRVM_PROPERTY_DEFS} = "-Duser.language=en -Duser.country=US";
$ENV{NLS_LANG}           = "AMERICAN_AMERICA";

print "<<<oracle_listeners:sep(124)>>>\n";

# Load bakery-generated exclusion config (absent file = no exclusions).
my %config   = read_plugin_config();
my $excludes = $config{EXCLUDE};

# Discover all Oracle homes (for standard listener checks).
my @oracle_homes = find_oracle_homes();

# Discover running listeners from tnslsnr processes / Windows services.
my @proc_listeners = scan_listener_processes();

# Build unified listener list: process scan first, oratab fallback second.
my %seen_lsnr;
my @all_listeners;

for my $pl (@proc_listeners)
{
    if ( $pl->{ORAHOME} )
    {
        my $key = lc("$pl->{NAME}:$pl->{ORAHOME}");
        next if $seen_lsnr{$key}++;
        push @all_listeners, $pl;
    }
    else
    {
        # Windows: orahome was not resolved from the service binary path;
        # fall back to checking the listener name against every known home.
        for my $home (@oracle_homes)
        {
            my $key = lc("$pl->{NAME}:$home");
            next if $seen_lsnr{$key}++;
            push @all_listeners, { NAME => $pl->{NAME}, ORAHOME => $home };
        }
    }
}

# Parse listener.ora for each Oracle home to discover configured listener names,
# including non-default names and listeners that are currently stopped.
for my $home (@oracle_homes)
{
    for my $lsnrname ( find_listeners_from_listener_ora($home) )
    {
        my $key = lc("$lsnrname:$home");
        next if $seen_lsnr{$key}++;
        push @all_listeners, { NAME => $lsnrname, ORAHOME => $home };
    }
}

# Final fallback: if listener.ora was absent or empty, probe the default listener.
for my $home (@oracle_homes)
{
    my $key = lc("listener:$home");
    next if $seen_lsnr{$key}++;
    push @all_listeners, { NAME => "LISTENER", ORAHOME => $home };
}

# Metric 3000: check each standard listener.
for my $lsnr (@all_listeners)
{
    next if is_excluded( $lsnr->{NAME}, $lsnr->{ORAHOME}, $excludes );
    print format_output_line( metric3000( $lsnr->{ORAHOME}, $lsnr->{NAME} ) );
}

# Metrics 3010 / 3020: check RAC SCAN and management listeners.
my %grid_checked;
for my $home ( find_grid_homes() )
{
    next if $grid_checked{$home}++;

    # SCAN listeners (one output line per listener found).
    for my $r ( metric3010($home) )
    {
        my ($lsnrname) = ( ( $r->{OPTION1} // "" ) =~ /^LSNRNAME=(.*)/ );
        next if $lsnrname && is_excluded( $lsnrname, $home, $excludes );
        print format_output_line($r);
    }

    # Management listener (Oracle 12c+ Grid Infrastructure only).
    my $mgmt = metric3020($home);
    if ( defined $mgmt && !is_excluded( "MGMTLSNR", $home, $excludes ) )
    {
        print format_output_line($mgmt);
    }
}
