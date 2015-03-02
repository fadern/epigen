import random
from math import exp, log, sqrt, pi
from epigen.plink.util import sample_categorical, joint_maf

##
# The parameters that does not changed between models.
# 
class FixedParams:
    def __init__(self, maf, ld, sample_size, sample_maf = False):
        self.maf = maf
        self.ld = ld
        self.sample_size = sample_size
        self.sample_maf = sample_maf

    def get_maf(self):
        if not self.sample_maf:
            return joint_maf( self.maf, self.ld )
        else:
            start = self.maf[ 0 ]
            end = self.maf[ 1 ] - start

            m1 = start + end * random.random( )
            m2 = start + end * random.random( )

            return joint_maf( [ m1, m2 ], self.ld )

    def num_samples(self):
        return self.sample_size[ 0 ]

    def num_cases(self):
        return self.sample_size[ 0 ]

    def num_controls(self):
        return self.sample_size[ 1 ]

##
# This class represents a binary model that is used to first generate
# a phenotype, and then generate the genotypes.
#
class BinomialModel:
    def generate_phenotype(self, fixed_params):
        return [ 1 ] * fixed_params.num_cases( ) + [ 0 ] * fixed_params.num_controls( )

    def joint_prob(self, maf, penetrance, phenotype):
        geno_prob = [ p * f for p, f in zip( penetrance, maf ) ]
        geno_denom = sum( geno_prob )

        return [ g / geno_denom for g in geno_prob ]

    def generate_genotype(self, fixed_params, params, phenotype):
        maf = fixed_params.get_maf( )
        prob = [ ]
        prob.append( self.joint_prob( maf, params.penetrance, 1 ) )
        prob.append( self.joint_prob( maf, params.penetrance, 0 ) )

        snp1_list = list( )
        snp2_list = list( )
        for pheno in phenotype:
            snp1, snp2 =  sample_categorical( prob[ pheno ] )
            snp1_list.append( snp1 )
            snp2_list.append( snp2 )

        return snp1_list, snp2_list

    def is_binary(self):
        return True

class BinomialPhenoGenerator:
    def __init__(self, mu_map):
        self.mu_map = mu_map

    def generate_pheno(self, variants):
        mu = self.mu_map.map( variants )
        p = random.random( )
        return int( p <= mu )

class BinomialParams:
    def __init__(self, penetrance):
        self.penetrance = penetrance
    
##
# This class represents a continuous model that is used to first generate
# a phenotype, and then generate the genotypes.
#
class NormalModel:
    def __init__(self, mu, std, maf):
        self.mu = mu
        self.std = std
        self.maf = joint_maf( maf, None )

    def generate_phenotype(self, fixed_params):
        mu = sum( ( m * f for m, f in zip( self.mu, self.maf ) ) )
        mu2 = sum( ( m**2 * f for m, f in zip( self.mu, self.maf ) ) )
        std2 = sum( ( s**2 * f for s, f in zip( self.std, self.maf ) ) )

        total_std = sqrt( mu2 - mu**2 + std2 )

        return [ random.normalvariate( mu, total_std ) for i in range( fixed_params.num_samples( ) ) ]

    def normpdf(x, mean, sd):
        var = float( sd )**2
        denom = ( 2 * pi * var )**.5
        num = exp( -( x - mean )**2 / ( 2*var ) )
        return num / denom

    def joint_prob(self, mu, std, maf, pheno):
        geno_prob = [ self.normpdf( pheno, m, s ) * f for m, s, f in zip( mu, std, maf ) ]
        geno_denom = sum( geno_prob )

        return [ g / geno_denom for g in geno_prob ]

    def generate_genotype(self, fixed_params, params, phenotype):
        snp1_list = list( )
        snp2_list = list( )
        maf = fixed_params.get_maf( )
        for pheno in phenotype:
            prob_geno = self.joint_prob( params.mu, params.std, maf, pheno )
            snp1, snp2 = sample_categorical( prob_geno )
            
            snp1_list.append( snp1 )
            snp2_list.append( snp2 )

        return snp1_list, snp2_list
    
    def is_binary(self):
        return False

class NormalPhenoGenerator:
    def __init__(self, mu_map, dispersion):
        self.mu_map = mu_map
        self.dispersion = dispersion

    def generate_pheno(self, variants):
        mu = self.mu_map.map( variants )
        return random.normalvariate( mu, self.dispersion )

class NormalParams:
    def __init__(self, mu, std):
        self.mu = mu
        self.std = std

# Map variants to means

class GeneralMuMap:
    def __init__(self, mu):
        self.mu = mu

    def map(self, variants):
        if 3 in variants or len( variants ) != 2:
            return None
        else:
            return self.mu[ 3 * variants[ 0 ] + variants[ 1 ] ]

class AdditiveMuMap:
    def __init__(self, beta0, beta, link):
        self.beta0 = beta0
        self.beta = beta
        self.link = link

    def map(self, variants):
        if 3 in variants or len( variants ) != len( self.beta ):
            return None
        else:
            return self.link( beta0 + sum( v * b for v, b in zip( variants, self.beta ) ) )

def get_pheno_generator(model, mu_map, dispersion):
    if model == "normal":
        return NormalPhenoGenerator( mu_map, dispersion )
    elif model == "binomial":
        return BinomialPhenoGenerator( mu_map )
    else:
        raise ValueError( "No such model {0}.".format( model ) )

def get_models():
    return [ "normal", "binomial" ]

def get_links():
    return {
        "identity" : lambda x: x,
        "log" : exp,
        "exp" : log,
        "logc" : lambda x: 1 - exp( x ),
        "odds" : lambda x: x/(1+x),
        "logodds" : lambda x: 1/(1+exp(-x)) }

def get_link_names():
    return get_links( ).keys( )

def get_link(link_str):
    return get_links( ).get( link_str, None )

def get_mean_values(beta, lf):
    P = [ [ 1, 0, 0, 0, 0, 0, 0, 0, 0 ],
          [ 1, 1, 0, 0, 0, 0, 0, 0, 0 ],
          [ 1, 0, 1, 0, 0, 0, 0, 0, 0 ],
          [ 1, 0, 0, 1, 0, 0, 0, 0, 0 ],
          [ 1, 1, 0, 1, 0, 1, 0, 0, 0 ],
          [ 1, 0, 1, 1, 0, 0, 1, 0, 0 ],
          [ 1, 0, 0, 0, 1, 0, 0, 0, 0 ],
          [ 1, 1, 0, 0, 1, 0, 0, 1, 0 ],
          [ 1, 0, 1, 0, 1, 0, 0, 0, 1 ] ]
    
    mu = [ ]
    for row in P:
        mu.append( lf( sum( r * b for r, b in zip( row, beta ) ) ) )

    return mu

def get_model_and_params(model, mu, std, maf):
    if model == "normal":
        return NormalModel( mu, [ std ] * 9, maf ), NormalParams( mu, [ std ] * 9 )
    elif model == "binomial":
        return BinomialModel( ), BinomialParams( mu ) 
    else:
        raise ValueError( "Unknown model {0}".format( model ) )